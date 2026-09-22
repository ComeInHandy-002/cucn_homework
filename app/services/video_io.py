"""Capability-detected video I/O for the inference pipeline.

FFmpeg is optional because the desktop demo may be started before a bundled
FFmpeg build is installed.  ``auto`` prefers FFmpeg and NVENC/NVDEC when the
binary advertises them, then falls back to OpenCV without changing the
pipeline contract.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    total_frames: int


@dataclass(frozen=True)
class FFmpegCapabilities:
    available: bool
    nvdec: bool = False
    nvenc: bool = False
    version: str | None = None
    error: str | None = None


def _resolve_binary(configured: str) -> str | None:
    path = Path(configured)
    if path.is_file():
        return str(path)
    return shutil.which(configured)


def probe_ffmpeg(ffmpeg_binary: str, ffprobe_binary: str) -> FFmpegCapabilities:
    """Inspect binaries without failing application startup."""

    ffmpeg = _resolve_binary(ffmpeg_binary)
    if ffmpeg is None:
        return FFmpegCapabilities(available=False, error=f"FFmpeg executable not found: {ffmpeg_binary}")
    try:
        version_process = subprocess.run(
            [ffmpeg, "-hide_banner", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        version_line = (version_process.stdout or "").splitlines()[0] if version_process.stdout else None
        hwaccel_process = subprocess.run(
            [ffmpeg, "-hide_banner", "-hwaccels"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        encoder_process = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        hwaccels = f"{hwaccel_process.stdout}\n{hwaccel_process.stderr}".lower()
        encoders = f"{encoder_process.stdout}\n{encoder_process.stderr}".lower()
        # NVDEC is exposed as the CUDA hwaccel on current FFmpeg builds.  A
        # separate nvdec token is accepted for older vendor builds.
        return FFmpegCapabilities(
            available=version_process.returncode == 0,
            nvdec="cuda" in hwaccels or "nvdec" in hwaccels,
            nvenc="h264_nvenc" in encoders,
            version=version_line,
            error=None if version_process.returncode == 0 else (version_process.stderr or "FFmpeg probe failed"),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return FFmpegCapabilities(available=False, error=str(exc))


def _parse_rate(value: Any, default: float = 25.0) -> float:
    try:
        rate = float(Fraction(str(value)))
        return rate if rate > 0 else default
    except (ValueError, ZeroDivisionError):
        return default


def probe_metadata(path: Path, ffprobe_binary: str) -> VideoMetadata:
    binary = _resolve_binary(ffprobe_binary)
    if binary is None:
        raise RuntimeError(f"FFprobe executable not found: {ffprobe_binary}")
    process = subprocess.run(
        [
            binary,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError((process.stderr or "FFprobe failed").strip())
    payload = json.loads(process.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError("FFprobe did not find a video stream")
    stream = streams[0]
    fps = _parse_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
    total = 0
    try:
        total = max(0, int(stream.get("nb_frames") or 0))
    except (TypeError, ValueError):
        total = 0
    if total == 0:
        try:
            total = max(0, int(round(float(stream.get("duration")) * fps)))
        except (TypeError, ValueError):
            total = 0
    return VideoMetadata(
        width=max(1, int(stream.get("width") or 0)),
        height=max(1, int(stream.get("height") or 0)),
        fps=fps,
        total_frames=total,
    )


class OpenCVReader:
    backend = "opencv"

    def __init__(self, path: Path) -> None:
        try:
            import cv2  # type: ignore
        except Exception as exc:
            raise RuntimeError("OpenCV is required for video decoding") from exc
        self._cap = cv2.VideoCapture(str(path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Unable to open video file: {path}")
        self.metadata = VideoMetadata(
            width=int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            height=int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            fps=float(self._cap.get(cv2.CAP_PROP_FPS) or 25.0),
            total_frames=int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
        )

    def read(self) -> Any | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        self._cap.release()


class FFmpegReader:
    def __init__(self, path: Path, metadata: VideoMetadata, binary: str, use_nvdec: bool) -> None:
        try:
            import numpy as np  # type: ignore
        except Exception as exc:
            raise RuntimeError("NumPy is required for FFmpeg rawvideo decoding") from exc
        self._np = np
        self.metadata = metadata
        self.backend = "ffmpeg-nvdec" if use_nvdec else "ffmpeg"
        self._frame_bytes = metadata.width * metadata.height * 3
        self._eof_reached = False
        command = [binary, "-nostdin", "-hide_banner", "-loglevel", "error"]
        if use_nvdec:
            command += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
        command += ["-i", str(path), "-an"]
        if use_nvdec:
            # CUDA frames must first be downloaded in a hardware-supported
            # surface format before the ordinary scaler converts to BGR.
            command += ["-vf", "hwdownload,format=nv12,format=bgr24"]
        command += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-vsync", "0", "pipe:1"]
        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as exc:
            raise RuntimeError(f"Unable to start FFmpeg decoder: {exc}") from exc
        self._prefetched = self._read_frame()
        if self._prefetched is None:
            return_code = self._process.poll()
            stderr = self._stderr_text()
            self._terminate_quietly()
            raise RuntimeError(
                f"FFmpeg decoder produced no frames ({return_code}): {stderr or 'unknown decode error'}"
            )

    def _stderr_text(self) -> str:
        if self._process.stderr is None or self._process.poll() is None:
            return ""
        try:
            return self._process.stderr.read().decode("utf-8", errors="replace").strip()
        except (OSError, ValueError):
            return ""

    def _read_frame(self) -> Any | None:
        if self._process.stdout is None:
            return None
        chunks: list[bytes] = []
        remaining = self._frame_bytes
        while remaining:
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if not chunks:
            self._eof_reached = True
            return None
        data = b"".join(chunks)
        if len(data) != self._frame_bytes:
            raise RuntimeError("FFmpeg decoder returned a truncated frame")
        return self._np.frombuffer(data, dtype=self._np.uint8).reshape(
            (self.metadata.height, self.metadata.width, 3)
        ).copy()

    def read(self) -> Any | None:
        if self._prefetched is not None:
            frame = self._prefetched
            self._prefetched = None
            return frame
        return self._read_frame()

    def _terminate_quietly(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
        try:
            self._process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for stream in (self._process.stdout, self._process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

    def release(self) -> None:
        stdout = self._process.stdout
        if stdout is not None:
            stdout.close()
        try:
            return_code = self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            return_code = self._process.wait(timeout=5)
        if return_code != 0 and self._eof_reached:
            stderr = self._stderr_text()
            if stderr.strip():
                raise RuntimeError(f"FFmpeg decoder failed: {stderr.strip()}")
        if self._process.stderr is not None:
            self._process.stderr.close()


class OpenCVWriter:
    backend = "opencv"

    def __init__(self, path: Path, metadata: VideoMetadata) -> None:
        import cv2  # type: ignore

        self.path = path
        self._writer = None
        for suffix, codec in ((".webm", "VP80"), (".webm", "VP90"), (".mp4", "mp4v")):
            candidate = path.with_suffix(suffix)
            writer = cv2.VideoWriter(
                str(candidate),
                cv2.VideoWriter_fourcc(*codec),
                metadata.fps,
                (metadata.width, metadata.height),
            )
            if writer.isOpened():
                self.path = candidate
                self._writer = writer
                break
            writer.release()
        if self._writer is None:
            raise RuntimeError("Unable to create an OpenCV result video")

    def write(self, frame: Any) -> None:
        self._writer.write(frame)

    def release(self) -> None:
        self._writer.release()


class FFmpegWriter:
    backend = "ffmpeg"

    def __init__(self, path: Path, metadata: VideoMetadata, binary: str, use_nvenc: bool) -> None:
        self.path = path.with_suffix(".mp4")
        codec = "h264_nvenc" if use_nvenc else "libx264"
        preset = "p4" if use_nvenc else "veryfast"
        command = [
            binary,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s:v",
            f"{metadata.width}x{metadata.height}",
            "-r",
            f"{metadata.fps:.06f}",
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            codec,
            "-preset",
            preset,
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-y",
            str(self.path),
        ]
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as exc:
            raise RuntimeError(f"Unable to start FFmpeg encoder: {exc}") from exc
        self._codec = codec

    def write(self, frame: Any) -> None:
        if self._process.stdin is None:
            raise RuntimeError("FFmpeg encoder stdin is closed")
        try:
            self._process.stdin.write(frame.tobytes())
        except (AttributeError, BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"FFmpeg encoder stopped: {exc}") from exc

    def release(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()
        return_code = self._process.wait(timeout=30)
        stderr = self._process.stderr.read().decode("utf-8", errors="replace") if self._process.stderr else ""
        if self._process.stderr is not None:
            self._process.stderr.close()
        if return_code != 0:
            raise RuntimeError(f"FFmpeg encoder ({self._codec}) failed: {stderr.strip() or return_code}")


@lru_cache(maxsize=8)
def _encoder_works(binary: str, codec: str) -> bool:
    """Verify that FFmpeg can initialize an encoder, not merely list it."""

    try:
        process = subprocess.run(
            [
                binary,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                # Recent NVENC drivers reject frames below their minimum
                # supported dimensions; use a representative tiny frame.
                "color=c=black:s=256x256:r=1",
                "-frames:v",
                "1",
                "-c:v",
                codec,
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        return process.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def open_reader(path: Path, backend: str, ffmpeg_binary: str, ffprobe_binary: str) -> tuple[Any, FFmpegCapabilities]:
    capabilities = probe_ffmpeg(ffmpeg_binary, ffprobe_binary)
    if backend in {"auto", "ffmpeg"} and capabilities.available:
        binary = _resolve_binary(ffmpeg_binary) or ffmpeg_binary
        try:
            metadata = probe_metadata(path, ffprobe_binary)
        except Exception:
            if backend == "ffmpeg":
                raise
        else:
            if capabilities.nvdec:
                try:
                    return FFmpegReader(path, metadata, binary, True), capabilities
                except Exception:
                    pass
            try:
                return FFmpegReader(path, metadata, binary, False), capabilities
            except Exception:
                if backend == "ffmpeg":
                    raise
    return OpenCVReader(path), capabilities


def open_writer(
    path: Path,
    metadata: VideoMetadata,
    backend: str,
    capabilities: FFmpegCapabilities,
    ffmpeg_binary: str,
) -> tuple[Any, str]:
    if backend in {"auto", "ffmpeg"} and capabilities.available:
        binary = _resolve_binary(ffmpeg_binary) or ffmpeg_binary
        try:
            use_nvenc = capabilities.nvenc and _encoder_works(binary, "h264_nvenc")
            codec = "h264_nvenc" if use_nvenc else "libx264"
            if not _encoder_works(binary, codec):
                raise RuntimeError(f"FFmpeg encoder is unavailable: {codec}")
            writer = FFmpegWriter(path, metadata, binary, use_nvenc)
            return writer, "ffmpeg-nvenc" if use_nvenc else "ffmpeg"
        except Exception:
            if backend == "ffmpeg":
                raise
    writer = OpenCVWriter(path, metadata)
    return writer, writer.backend
