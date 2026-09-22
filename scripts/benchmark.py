from __future__ import annotations

import time

from app.core.detector import FallbackDetector
from app.core.rules import SafetyRuleEngine
from app.core.tracker import ByteTrackTracker


def main() -> None:
    frames = 300
    detector = FallbackDetector(scenario="no_ppe")
    tracker = ByteTrackTracker()
    rules = SafetyRuleEngine(confirmation_frames=3, cooldown_seconds=10)
    started = time.perf_counter()
    event_count = 0
    for index in range(frames):
        detections = detector.detect(b"synthetic-frame", frame_index=index)
        tracked = tracker.update(detections, frame_index=index)
        event_count += len(rules.evaluate_frame(tracked))
    elapsed = time.perf_counter() - started
    print(f"frames={frames} elapsed={elapsed:.4f}s fps={frames / elapsed:.2f} events={event_count}")


if __name__ == "__main__":
    main()
