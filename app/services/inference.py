"""Inference orchestration for image and video jobs."""

from __future__ import annotations

import json
import queue
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread, local
from time import perf_counter
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.core.detector import FallbackDetector, YOLODetector
from app.core.rules import SafetyRuleEngine
from app.core.schemas import DangerZone, Detection, FrameResult, InferenceResult, JobStatus, SafetyEvent, SourceType
from app.core.tracker import ByteTrackTracker
from app.db.database import SessionLocal
from app.db.models import DangerZoneRecord, InferenceJobRecord, SafetyEventRecord
from app.services.video_io import open_reader, open_writer, probe_ffmpeg


def enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _DecodedFrame:
    frame_index: int
    timestamp: datetime
    frame: Any


@dataclass
class _InferenceFrame:
    frame_index: int
    timestamp: datetime
    frame: Any
    detections: list[Detection]


@dataclass
class _PipelineFailure:
    error: BaseException


_PIPELINE_END = object()


class InferenceService:
    def __init__(self) -> None:
        self.detector = self._new_detector()
        self._worker_local = local()
        self._executor_lock = Lock()
        self._shared_detector_lock = Lock()
        self._video_executor: ThreadPoolExecutor | None = None
        self._video_futures: set[Future[Any]] = set()
        # Direct/synchronous calls use the already-loaded image detector.  A
        # queued multi-video run fixes its worker count once and then gives
        # every executor thread its own detector instance.
        self._video_worker_limit = 1

    def _new_detector(self) -> YOLODetector:
        return YOLODetector(
            model_path=settings.model_path,
            confidence=settings.model_confidence,
            device=settings.model_device or None,
            fallback=FallbackDetector(scenario=settings.fallback_scenario),
            allow_download=settings.allow_model_download,
            image_size=settings.model_image_size,
            half=settings.video_half,
            batch_size=settings.video_batch_size,
            tensorrt=settings.video_tensorrt,
        )

    def _effective_video_workers(self) -> int:
        requested = min(settings.queue_workers, settings.max_video_workers)
        if requested <= 1:
            return 1
        # Each concurrent worker owns a separate Ultralytics model instance.
        # Use the currently free CUDA memory as a conservative upper bound;
        # if torch/CUDA is unavailable, serial execution is the safe choice.
        try:
            import torch  # type: ignore

            if not torch.cuda.is_available():
                return 1
            free_bytes, _ = torch.cuda.mem_get_info()
            memory_limit = max(1, int(free_bytes // (settings.video_worker_memory_mb * 1024 * 1024)))
            return max(1, min(requested, memory_limit))
        except Exception:
            return 1

    def _video_detector(self) -> YOLODetector:
        if self._video_worker_limit <= 1:
            return self.detector
        detector = getattr(self._worker_local, "detector", None)
        if detector is None:
            detector = self._new_detector()
            self._worker_local.detector = detector
        return detector

    def detector_info(self) -> dict[str, Any]:
        capabilities = probe_ffmpeg(settings.ffmpeg_binary, settings.ffprobe_binary)
        return {
            "backend": self.detector.backend,
            "available": self.detector.available,
            "load_error": self.detector.load_error,
            "model_path": str(self.detector.model_path) if isinstance(self.detector.model_path, (str, Path)) else "<in-memory>",
            "image_size": self.detector.image_size,
            "batch_size": self.detector.batch_size,
            "half_requested": self.detector.half_requested,
            "half_enabled": self.detector.half_enabled,
            "tensorrt_requested": self.detector.tensorrt_requested,
            "tensorrt_active": self.detector.tensorrt_active,
            "video_decode_backend": settings.video_decode_backend,
            "video_encode_backend": settings.video_encode_backend,
            "video_queue_size": settings.video_queue_size,
            "queue_workers_requested": settings.queue_workers,
            "queue_workers_effective": self._video_worker_limit if self._video_executor else self._effective_video_workers(),
            "ffmpeg_available": capabilities.available,
            "ffmpeg_nvdec": capabilities.nvdec,
            "ffmpeg_nvenc": capabilities.nvenc,
        }

    def process_image(self, db: Session, source_path: Path, camera_id: str | None = None) -> InferenceResult:
        job = InferenceJobRecord(
            source_type=SourceType.IMAGE.value,
            source_path=str(source_path),
            status=JobStatus.RUNNING.value,
            progress=5.0,
            camera_id=camera_id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        try:
            frame = self._load_image(source_path)
            tracker = ByteTrackTracker()
            zones = self._zones_for_camera(db, camera_id)
            # A single image has no temporal sequence, so image mode confirms on one frame.
            rules = SafetyRuleEngine(zones=zones, confirmation_frames=1, cooldown_seconds=10.0)
            # Still images have no temporal confirmation, so use the stricter
            # PPE evidence floor and let the rule engine report uncertainty as
            # a missing item instead of accepting a weak background box.
            with self._shared_detector_lock:
                raw_detections = self.detector.detect(frame, frame_index=0, strict_ppe=True)
            detections = tracker.update(raw_detections, frame_index=0)
            timestamp = utc_now()
            events = rules.evaluate_frame(detections, camera_id=camera_id, timestamp=timestamp)
            annotated_path = self._write_image_annotation(source_path, detections, events)
            for event in events:
                event.evidence_path = str(annotated_path)
            self._persist_events(db, events)
            frame_result = FrameResult(frame_index=0, timestamp=timestamp, detections=detections, events=events)
            result = InferenceResult(
                job_id=job.id,
                source_type=SourceType.IMAGE,
                frames=[frame_result],
                detections=detections,
                events=events,
                result_path=None,
                preview_path=str(annotated_path),
            )
            result_path = self._write_result_json(job.id, result)
            result.result_path = str(result_path)
            job.status = JobStatus.COMPLETED.value
            job.progress = 100.0
            job.result_path = str(result_path)
            job.updated_at = utc_now()
            db.commit()
            return result
        except Exception as exc:
            job.status = JobStatus.FAILED.value
            job.error_message = str(exc)
            job.updated_at = utc_now()
            db.commit()
            raise

    def create_video_job(self, db: Session, source_path: Path, camera_id: str | None = None) -> InferenceJobRecord:
        job = InferenceJobRecord(
            source_type=SourceType.VIDEO.value,
            source_path=str(source_path),
            status=JobStatus.QUEUED.value,
            progress=0.0,
            camera_id=camera_id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def run_video_job(self, job_id: str) -> None:
        """Run one job synchronously; useful for scripts and deterministic tests."""

        db = SessionLocal()
        try:
            job = db.get(InferenceJobRecord, job_id)
            if job is None:
                return
            job.status = JobStatus.RUNNING.value
            job.progress = 1.0
            job.updated_at = utc_now()
            db.commit()
            result = self._process_video(db, job)
            result_path = self._write_result_json(job.id, result)
            job.status = JobStatus.COMPLETED.value
            job.progress = 100.0
            job.result_path = str(result_path)
            job.updated_at = utc_now()
            db.commit()
        except Exception as exc:
            job = db.get(InferenceJobRecord, job_id)
            if job is not None:
                job.status = JobStatus.FAILED.value
                job.error_message = str(exc)
                job.updated_at = utc_now()
                db.commit()
        finally:
            db.close()

    def enqueue_video_job(self, job_id: str) -> None:
        """Submit a job to a bounded, model-isolated video worker pool."""

        with self._executor_lock:
            if self._video_executor is None:
                self._video_worker_limit = self._effective_video_workers()
                self._video_executor = ThreadPoolExecutor(
                    max_workers=self._video_worker_limit,
                    thread_name_prefix="safety-video",
                )
            future = self._video_executor.submit(self.run_video_job, job_id)
            self._video_futures.add(future)
            future.add_done_callback(self._video_futures.discard)

    def _process_video(self, db: Session, job: InferenceJobRecord) -> InferenceResult:
        try:
            import cv2  # type: ignore
        except Exception as exc:
            raise RuntimeError("OpenCV is required for video annotation; install opencv-python") from exc

        source_path = Path(job.source_path)
        reader, capabilities = open_reader(
            source_path,
            settings.video_decode_backend,
            settings.ffmpeg_binary,
            settings.ffprobe_binary,
        )
        metadata = reader.metadata
        writer = None
        video_path: Path | None = None
        encode_backend = "none"
        if metadata.width > 0 and metadata.height > 0:
            writer, encode_backend = open_writer(
                settings.result_dir / f"{job.id}_annotated.mp4",
                metadata,
                settings.video_encode_backend,
                capabilities,
                settings.ffmpeg_binary,
            )
            video_path = Path(writer.path)

        decode_queue: queue.Queue[Any] = queue.Queue(maxsize=settings.video_queue_size)
        inference_queue: queue.Queue[Any] = queue.Queue(maxsize=settings.video_queue_size)
        failure_queue: queue.Queue[_PipelineFailure] = queue.Queue(maxsize=1)
        stop_event = Event()
        done_event = Event()
        reader_released = Event()
        writer_released = Event()
        timings = {"decode": 0.0, "inference": 0.0, "encode": 0.0}
        runtime_info = {"half": False, "tensorrt": False, "detector_backend": "unknown"}

        tracker = ByteTrackTracker(min_confirmed_hits=3)
        zones = self._zones_for_camera(db, job.camera_id)
        rules = SafetyRuleEngine(
            zones=zones,
            confirmation_frames=3,
            cooldown_seconds=10.0,
            ppe_grace_frames=15,
            ppe_warmup_frames=15,
        )
        frames: list[FrameResult] = []
        all_events: list[SafetyEvent] = []
        all_detections: list[Detection] = []

        def signal_failure(error: BaseException) -> None:
            try:
                failure_queue.put_nowait(_PipelineFailure(error))
            except queue.Full:
                pass
            stop_event.set()

        def put_bounded(target: queue.Queue[Any], item: Any) -> bool:
            while not stop_event.is_set():
                try:
                    target.put(item, timeout=0.2)
                    return True
                except queue.Full:
                    continue
            return False

        def decode_worker() -> None:
            frame_index = 0
            try:
                while not stop_event.is_set():
                    started = perf_counter()
                    frame = reader.read()
                    timings["decode"] += perf_counter() - started
                    if frame is None:
                        break
                    packet = _DecodedFrame(frame_index=frame_index, timestamp=utc_now(), frame=frame)
                    if not put_bounded(decode_queue, packet):
                        break
                    frame_index += 1
            except BaseException as exc:
                signal_failure(exc)
            finally:
                put_bounded(decode_queue, _PIPELINE_END)
                try:
                    reader.release()
                except BaseException as exc:
                    signal_failure(exc)
                reader_released.set()

        def inference_worker() -> None:
            try:
                detector = self._video_detector()
                runtime_info["half"] = detector.half_enabled
                runtime_info["tensorrt"] = detector.tensorrt_active
                runtime_info["detector_backend"] = detector.backend
                while not stop_event.is_set():
                    try:
                        first = decode_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if first is _PIPELINE_END:
                        break
                    batch = [first]
                    reached_end = False
                    while len(batch) < settings.video_batch_size:
                        try:
                            item = decode_queue.get(timeout=0.02)
                        except queue.Empty:
                            break
                        if item is _PIPELINE_END:
                            reached_end = True
                            break
                        batch.append(item)
                    started = perf_counter()
                    if detector is self.detector:
                        with self._shared_detector_lock:
                            detections = detector.detect_batch(
                                [item.frame for item in batch],
                                [item.frame_index for item in batch],
                            )
                    else:
                        detections = detector.detect_batch(
                            [item.frame for item in batch],
                            [item.frame_index for item in batch],
                        )
                    timings["inference"] += perf_counter() - started
                    if len(detections) != len(batch):
                        raise RuntimeError("batch detector returned an unexpected frame count")
                    for item, frame_detections in zip(batch, detections):
                        if not put_bounded(
                            inference_queue,
                            _InferenceFrame(item.frame_index, item.timestamp, item.frame, frame_detections),
                        ):
                            return
                    if reached_end:
                        break
            except BaseException as exc:
                signal_failure(exc)
            finally:
                put_bounded(inference_queue, _PIPELINE_END)

        def process_ordered_worker() -> None:
            pending: dict[int, _InferenceFrame] = {}
            next_index = 0

            def process_packet(packet: _InferenceFrame) -> None:
                nonlocal next_index
                detections = tracker.update(packet.detections, frame_index=packet.frame_index)
                events = rules.evaluate_frame(
                    detections,
                    camera_id=job.camera_id,
                    timestamp=packet.timestamp,
                )
                if events:
                    evidence_path = settings.result_dir / f"{job.id}_frame_{packet.frame_index:06d}.jpg"
                    cv2.imwrite(str(evidence_path), self._annotate_cv2_frame(packet.frame.copy(), detections, events))
                    for event in events:
                        event.evidence_path = str(evidence_path)
                    self._persist_events(db, events)
                    all_events.extend(events)
                started = perf_counter()
                annotated = self._annotate_cv2_frame(packet.frame, detections, events)
                if writer is not None:
                    writer.write(annotated)
                timings["encode"] += perf_counter() - started
                all_detections.extend(detections)
                frames.append(
                    FrameResult(
                        frame_index=packet.frame_index,
                        timestamp=packet.timestamp,
                        detections=detections,
                        events=events,
                    )
                )
                next_index = packet.frame_index + 1
                if metadata.total_frames and next_index % 10 == 0:
                    job.progress = min(99.0, next_index / metadata.total_frames * 100.0)
                    job.updated_at = utc_now()
                    db.commit()

            try:
                while not stop_event.is_set():
                    try:
                        item = inference_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if item is _PIPELINE_END:
                        break
                    pending[item.frame_index] = item
                    while next_index in pending:
                        process_packet(pending.pop(next_index))
                # A missing index means an upstream failure; do not silently
                # hand tracker state a reordered or partial stream.
                if pending and not stop_event.is_set():
                    raise RuntimeError(f"ordered pipeline gap at frame {next_index}")
            except BaseException as exc:
                signal_failure(exc)
            finally:
                if writer is not None:
                    try:
                        writer.release()
                    except BaseException as exc:
                        signal_failure(exc)
                    writer_released.set()
                done_event.set()

        threads = [
            Thread(target=decode_worker, name="safety-decode", daemon=True),
            Thread(target=inference_worker, name="safety-inference", daemon=True),
            Thread(target=process_ordered_worker, name="safety-encode", daemon=True),
        ]
        pipeline_started = perf_counter()
        try:
            for thread in threads:
                thread.start()
            while not done_event.wait(0.2):
                if not failure_queue.empty():
                    stop_event.set()
                    break
        finally:
            stop_event.set()
            for thread in threads:
                thread.join(timeout=10)
            if not reader_released.is_set():
                try:
                    reader.release()
                except Exception:
                    pass
            if writer is not None and not writer_released.is_set():
                try:
                    writer.release()
                except Exception:
                    pass
        wall_seconds = perf_counter() - pipeline_started

        failure = failure_queue.get_nowait() if not failure_queue.empty() else None
        if failure is not None:
            raise RuntimeError(f"video pipeline failed: {failure.error}") from failure.error

        return InferenceResult(
            job_id=job.id,
            source_type=SourceType.VIDEO,
            frames=frames,
            detections=all_detections,
            events=all_events,
            result_path=None,
            preview_path=str(video_path) if video_path else None,
            metrics={
                "decode_backend": getattr(reader, "backend", "unknown"),
                "encode_backend": encode_backend,
                "detector_backend": runtime_info["detector_backend"],
                "batch_size": settings.video_batch_size,
                "queue_size": settings.video_queue_size,
                "half": runtime_info["half"],
                "tensorrt": runtime_info["tensorrt"],
                "decoded_frames": len(frames),
                "decode_seconds": round(timings["decode"], 4),
                "inference_seconds": round(timings["inference"], 4),
                "encode_seconds": round(timings["encode"], 4),
                "wall_seconds": round(wall_seconds, 4),
                "decode_fps": round(len(frames) / max(timings["decode"], 1e-6), 3),
                "inference_fps": round(len(frames) / max(timings["inference"], 1e-6), 3),
                "encode_fps": round(len(frames) / max(timings["encode"], 1e-6), 3),
                "total_fps": round(len(frames) / max(wall_seconds, 1e-6), 3),
            },
        )

    def _zones_for_camera(self, db: Session, camera_id: str | None) -> list[DangerZone]:
        query = db.query(DangerZoneRecord).filter(DangerZoneRecord.enabled.is_(True))
        if camera_id is None:
            records = query.filter(DangerZoneRecord.camera_id.is_(None)).all()
        else:
            try:
                camera_key = int(camera_id)
            except (TypeError, ValueError):
                return []
            records = query.filter(DangerZoneRecord.camera_id == camera_key).all()
        return [
            DangerZone(
                id=str(record.id),
                name=record.name,
                camera_id=str(record.camera_id) if record.camera_id is not None else None,
                polygon=record.polygon,
                enabled=record.enabled,
            )
            for record in records
        ]

    def _persist_events(self, db: Session, events: list[SafetyEvent]) -> None:
        for event in events:
            record = SafetyEventRecord(
                event_type=enum_value(event.event_type),
                severity=enum_value(event.severity),
                camera_id=event.camera_id,
                track_id=event.track_id,
                timestamp=event.timestamp,
                evidence_path=event.evidence_path,
                status=enum_value(event.status),
                zone_id=event.zone_id,
                message=event.message,
                metadata_json=event.metadata,
            )
            db.add(record)
            db.flush()
            event.id = record.id
        if events:
            db.commit()

    @staticmethod
    def _load_image(path: Path) -> Any:
        try:
            from PIL import Image

            return Image.open(path).convert("RGB")
        except Exception:
            return path.read_bytes()

    def _write_image_annotation(self, source_path: Path, detections: list[Detection], events: list[SafetyEvent]) -> Path:
        output_path = settings.result_dir / f"{source_path.stem}_{uuid4().hex}_annotated.jpg"
        try:
            from PIL import Image, ImageDraw, ImageFont

            image = Image.open(source_path).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            for detection in detections:
                color = self._color_for_detection(detection)
                box = detection.bbox
                draw.rectangle((box.x1, box.y1, box.x2, box.y2), outline=color, width=3)
                label = f"{detection.class_name} {detection.confidence:.2f}"
                if detection.track_id is not None:
                    label += f" #{detection.track_id}"
                draw.text((box.x1, max(0, box.y1 - 14)), label, fill=color, font=font)
            if events:
                draw.text((10, 10), f"Events: {len(events)}", fill=(220, 20, 60), font=font)
            image.save(output_path)
        except Exception:
            output_path.write_bytes(source_path.read_bytes())
        return output_path

    @staticmethod
    def _annotate_cv2_frame(frame: Any, detections: list[Detection], events: list[SafetyEvent]) -> Any:
        import cv2  # type: ignore

        for detection in detections:
            box = detection.bbox
            color = (0, 180, 0) if detection.class_name != "person" else (255, 180, 0)
            cv2.rectangle(frame, (int(box.x1), int(box.y1)), (int(box.x2), int(box.y2)), color, 2)
            label = f"{detection.class_name} {detection.confidence:.2f}"
            if detection.track_id is not None:
                label += f" #{detection.track_id}"
            cv2.putText(frame, label, (int(box.x1), max(12, int(box.y1) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        if events:
            cv2.putText(frame, f"Safety events: {len(events)}", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    @staticmethod
    def _color_for_detection(detection: Detection) -> tuple[int, int, int]:
        colors = {
            "person": (52, 132, 240),
            "helmet": (0, 150, 80),
            "vest": (230, 160, 20),
        }
        return colors.get(detection.class_name.lower(), (180, 80, 180))

    @staticmethod
    def _write_result_json(job_id: str, result: InferenceResult) -> Path:
        path = settings.result_dir / f"{job_id}_result.json"
        payload = result.model_dump(mode="json")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


inference_service = InferenceService()
