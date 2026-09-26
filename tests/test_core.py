from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.detector import FallbackDetector, YOLODetector
from app.core.rules import SafetyRuleEngine, associate_ppe, point_in_polygon, scale_zones_to_frame
from app.core.schemas import BoundingBox, DangerZone, Detection, EventType, Point
from app.core.tracker import ByteTrackTracker


def person(track_id: int | None = None) -> Detection:
    return Detection(class_name="person", confidence=0.95, bbox=BoundingBox(x1=100, y1=50, x2=300, y2=450), track_id=track_id)


def test_fallback_detector_can_emit_missing_ppe_scene():
    detections = FallbackDetector(scenario="no_ppe").detect(b"frame", frame_index=0)
    assert [item.class_name for item in detections] == ["person"]


def test_yolo_adapter_keeps_business_classes_and_suppresses_nested_boxes():
    class Boxes:
        xyxy = [[28, 20, 270, 640], [58, 16, 199, 384], [244, 15, 480, 640], [130, 550, 190, 616], [113, 25, 171, 78]]
        conf = [0.90, 0.50, 0.88, 0.58, 0.80]
        cls = [6, 6, 6, 3, 0]

    class Result:
        boxes = Boxes()
        names = {0: "helmet", 3: "boots", 6: "Person"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert [item.class_name for item in detections] == ["person", "person", "helmet"]
    assert all(item.class_name != "boots" for item in detections)


def test_detector_filters_edge_person_hallucinations_and_unassociated_vest():
    class Boxes:
        # The second and third person boxes are frame-edge/background
        # hallucinations.  The vest in the wall area must not reach the API,
        # even when it has a high score; the low-score vest checks the
        # business confidence floor independently.
        xyxy = [
            [200, 80, 400, 450],
            [430, 0, 640, 480],
            [0, 0, 640, 480],
            [430, 20, 638, 460],
            [450, 250, 620, 400],
            [10, 10, 150, 150],
            [250, 220, 350, 350],
        ]
        conf = [0.90, 0.89, 0.95, 0.80, 0.01, 0.80, 0.88]
        cls = [6, 6, 6, 7, 7, 7, 7]

    class Result:
        boxes = Boxes()
        names = {6: "Person", 7: "vest"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert [(item.class_name, round(item.confidence, 2)) for item in detections] == [("person", 0.9), ("vest", 0.88)]


def test_detector_rejects_large_ppe_box_with_only_center_inside_person():
    class Boxes:
        xyxy = [[200, 80, 400, 450], [0, 100, 500, 350]]
        conf = [0.90, 0.88]
        cls = [6, 7]

    class Result:
        boxes = Boxes()
        names = {6: "Person", 7: "vest"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert [item.class_name for item in detections] == ["person"]


def test_detector_rejects_scene_sized_edge_person_without_ppe_context():
    class Boxes:
        # This shape is typical of a wall/sky hallucination: it starts at the
        # top edge and occupies most of the frame, but has no worker PPE.
        xyxy = [[92, 0, 632, 438]]
        conf = [0.80]
        cls = [6]

    class Result:
        boxes = Boxes()
        names = {6: "Person"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    assert YOLODetector(model_path=Model()).detect(b"frame") == []


def test_detector_rejects_low_confidence_tiny_background_person():
    class Boxes:
        # The first candidate is a small, nearly square background object
        # (vehicle/excavator-like).  The second is a low-confidence but
        # ordinary full-body worker and must remain available for PPE rules.
        xyxy = [[90, 170, 145, 224], [220, 80, 330, 400]]
        conf = [0.51, 0.52]
        cls = [6, 6]

    class Result:
        boxes = Boxes()
        names = {6: "Person"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert len(detections) == 1
    assert detections[0].bbox.x1 == 220


def test_detector_rejects_low_confidence_narrow_person_clipped_by_side_edge():
    class Boxes:
        # This is a tall but very narrow edge candidate (a clipped passer-by
        # or background object), not a complete PPE subject.  A confident
        # close-up at the same edge must still be allowed through.
        xyxy = [[0, 55, 48, 300], [0, 0, 240, 480]]
        conf = [0.49, 0.90]
        cls = [6, 6]

    class Result:
        boxes = Boxes()
        names = {6: "Person"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert len(detections) == 1
    assert detections[0].confidence == 0.90


def test_detector_rejects_low_confidence_edge_partial_person_without_ppe():
    class Boxes:
        # x=0, width=47, height=220 on a 640x480 frame: this is the narrow
        # edge strip seen in the city construction video, not a reliable PPE
        # subject.  The ordinary low-confidence worker remains valid.
        xyxy = [[0, 70, 47, 290], [220, 80, 330, 400]]
        conf = [0.45, 0.52]
        cls = [6, 6]

    class Result:
        boxes = Boxes()
        names = {6: "Person"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert len(detections) == 1
    assert detections[0].bbox.x1 == 220


def test_detector_keeps_edge_partial_person_when_ppe_supports_it():
    class Boxes:
        xyxy = [[0, 70, 47, 290], [6, 80, 40, 112], [4, 125, 42, 190]]
        conf = [0.45, 0.70, 0.65]
        cls = [6, 0, 7]

    class Result:
        boxes = Boxes()
        names = {0: "helmet", 6: "Person", 7: "vest"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert {item.class_name for item in detections} == {"person", "helmet", "vest"}


def test_detector_keeps_full_frame_closeup_when_both_ppe_boxes_support_it():
    class Boxes:
        xyxy = [[0, 0, 640, 480], [245, 15, 395, 125], [215, 150, 430, 350]]
        conf = [0.90, 0.88, 0.86]
        cls = [6, 0, 7]

    class Result:
        boxes = Boxes()
        names = {0: "helmet", 6: "Person", 7: "vest"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert {item.class_name for item in detections} == {"person", "helmet", "vest"}


def test_detector_keeps_high_confidence_upright_closeup_without_ppe():
    class Boxes:
        xyxy = [[120, 0, 520, 480]]
        conf = [0.96]
        cls = [6]

    class Result:
        boxes = Boxes()
        names = {6: "Person"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detections = YOLODetector(model_path=Model()).detect(b"frame")
    assert [item.class_name for item in detections] == ["person"]


def test_strict_image_mode_rejects_weak_ppe_box():
    class Boxes:
        xyxy = [[200, 80, 400, 450], [245, 85, 355, 145], [240, 180, 360, 300]]
        conf = [0.90, 0.08, 0.09]
        cls = [6, 0, 7]

    class Result:
        boxes = Boxes()
        names = {0: "helmet", 6: "Person", 7: "vest"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            return [Result()]

    detector = YOLODetector(model_path=Model())
    assert [item.class_name for item in detector.detect(b"frame", strict_ppe=True)] == ["person"]


def test_strict_image_mode_enables_test_time_augmentation_only_for_images():
    calls = []

    class Boxes:
        xyxy = [[200, 80, 400, 450]]
        conf = [0.90]
        cls = [6]

    class Result:
        boxes = Boxes()
        names = {6: "Person"}

    class Model:
        names = Result.names

        @staticmethod
        def predict(source, **kwargs):
            calls.append(kwargs)
            return [Result()]

    detector = YOLODetector(model_path=Model())
    detector.detect(b"frame", strict_ppe=True)
    detector.detect(b"frame", strict_ppe=False)
    assert calls[0].get("augment") is True
    assert "augment" not in calls[1]


def test_tracker_keeps_stable_person_id():
    tracker = ByteTrackTracker()
    first = tracker.update([person()], frame_index=0)[0]
    second = tracker.update([Detection(class_name="person", confidence=0.95, bbox=[105, 52, 305, 452])], frame_index=1)[0]
    assert first.track_id == second.track_id == 1


def test_tracker_hides_person_and_ppe_until_three_consecutive_hits():
    tracker = ByteTrackTracker(min_confirmed_hits=3)
    helmet = Detection(class_name="helmet", confidence=0.9, bbox=[145, 55, 255, 130])
    vest = Detection(class_name="vest", confidence=0.9, bbox=[135, 180, 265, 330])

    assert tracker.update([person(), helmet, vest], frame_index=0) == []
    assert tracker.update([person(), helmet, vest], frame_index=1) == []
    confirmed = tracker.update([person(), helmet, vest], frame_index=2)

    assert [item.class_name for item in confirmed] == ["person", "helmet", "vest"]
    assert confirmed[0].track_id == 1


def test_tracker_resets_confirmation_after_a_missed_frame():
    tracker = ByteTrackTracker(min_confirmed_hits=3)

    assert tracker.update([person()], frame_index=0) == []
    assert tracker.update([person()], frame_index=1) == []
    assert tracker.update([], frame_index=2) == []
    assert tracker.update([person()], frame_index=3) == []
    assert tracker.update([person()], frame_index=4) == []
    confirmed = tracker.update([person()], frame_index=5)

    assert len(confirmed) == 1
    assert confirmed[0].track_id == 1


def test_confirmed_tracker_remains_confirmed_after_brief_occlusion():
    tracker = ByteTrackTracker(min_confirmed_hits=3)
    for frame_index in range(3):
        tracker.update([person()], frame_index=frame_index)

    assert tracker.update([], frame_index=3) == []
    visible_again = tracker.update([person()], frame_index=4)

    assert len(visible_again) == 1
    assert visible_again[0].track_id == 1


def test_tracker_does_not_expose_ppe_for_nearer_unconfirmed_person():
    tracker = ByteTrackTracker(min_confirmed_hits=3)
    confirmed_person = Detection(class_name="person", confidence=0.95, bbox=[100, 50, 300, 450])
    for frame_index in range(3):
        tracker.update([confirmed_person], frame_index=frame_index)

    new_person = Detection(class_name="person", confidence=0.95, bbox=[220, 50, 420, 450])
    new_person_helmet = Detection(class_name="helmet", confidence=0.9, bbox=[285, 60, 365, 125])
    detections = tracker.update([confirmed_person, new_person, new_person_helmet], frame_index=3)

    assert [item.class_name for item in detections] == ["person"]
    assert detections[0].track_id == 1


def test_ppe_association_matches_expected_body_regions():
    worker = person(track_id=7)
    helmet = Detection(class_name="helmet", confidence=0.9, bbox=[145, 55, 255, 130])
    vest = Detection(class_name="vest", confidence=0.9, bbox=[135, 180, 265, 330])
    association = associate_ppe([worker], [worker, helmet, vest])[7]
    assert association.has_helmet
    assert association.has_vest


def test_point_in_polygon_counts_boundary_as_inside():
    square = [Point(x=0, y=0), Point(x=10, y=0), Point(x=10, y=10), Point(x=0, y=10)]
    assert point_in_polygon(Point(x=5, y=5), square)
    assert point_in_polygon(Point(x=10, y=5), square)
    assert not point_in_polygon(Point(x=12, y=5), square)


def test_rule_engine_requires_three_frames_and_cools_down():
    engine = SafetyRuleEngine(confirmation_frames=3, cooldown_seconds=10)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    detections = [person(track_id=1)]
    assert engine.evaluate_frame(detections, timestamp=base) == []
    assert engine.evaluate_frame(detections, timestamp=base + timedelta(seconds=1)) == []
    events = engine.evaluate_frame(detections, timestamp=base + timedelta(seconds=2))
    assert {event.event_type for event in events} == {EventType.NO_HELMET, EventType.NO_VEST}
    assert engine.evaluate_frame(detections, timestamp=base + timedelta(seconds=3)) == []
    assert engine.evaluate_frame(detections, timestamp=base + timedelta(seconds=13))


def test_video_rule_engine_graces_short_ppe_dropout_and_warms_new_tracks():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    worker = person(track_id=8)
    helmet = Detection(class_name="helmet", confidence=0.8, bbox=[145, 55, 255, 130])
    vest = Detection(class_name="vest", confidence=0.8, bbox=[135, 180, 265, 330])
    engine = SafetyRuleEngine(
        confirmation_frames=3,
        cooldown_seconds=10,
        ppe_grace_frames=2,
        ppe_warmup_frames=2,
    )
    # Warm-up and a short detector dropout must not create missing-PPE events.
    assert engine.evaluate_frame([worker, helmet, vest], timestamp=base) == []
    assert engine.evaluate_frame([worker], timestamp=base + timedelta(seconds=1)) == []
    assert engine.evaluate_frame([worker], timestamp=base + timedelta(seconds=2)) == []
    assert engine.evaluate_frame([worker], timestamp=base + timedelta(seconds=3)) == []


def test_ppe_grace_counts_track_observations_not_global_frames():
    """Occlusion frames must not consume a tracked worker's PPE grace window."""

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    worker = person(track_id=9)
    helmet = Detection(class_name="helmet", confidence=0.8, bbox=[145, 55, 255, 130])
    vest = Detection(class_name="vest", confidence=0.8, bbox=[135, 180, 265, 330])
    engine = SafetyRuleEngine(
        confirmation_frames=3,
        cooldown_seconds=10,
        ppe_grace_frames=2,
        ppe_warmup_frames=0,
    )

    assert engine.evaluate_frame([worker, helmet, vest], timestamp=base) == []
    # The track is not observable during an occlusion.  These frames should
    # not make the last confirmed PPE state stale.
    for index in range(10):
        assert engine.evaluate_frame([], timestamp=base + timedelta(seconds=index + 1)) == []

    # Three observed dropouts are still inside the grace window plus the
    # confirmation period.  The old global-frame implementation emitted here.
    for index in range(3):
        assert engine.evaluate_frame([worker], timestamp=base + timedelta(seconds=index + 11)) == []

    # A sustained absence is still eventually reported once grace and
    # confirmation have both elapsed.
    emitted = []
    for index in range(3, 7):
        emitted.extend(engine.evaluate_frame([worker], timestamp=base + timedelta(seconds=index + 11)))
    assert {event.event_type for event in emitted} == {EventType.NO_HELMET, EventType.NO_VEST}


def test_positive_ppe_evidence_wins_over_conflicting_negative_classes():
    """A weak negative class must not override same-track PPE evidence."""

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    worker = person(track_id=10)
    helmet = Detection(class_name="helmet", confidence=0.8, bbox=[145, 55, 255, 130])
    vest = Detection(class_name="vest", confidence=0.8, bbox=[135, 180, 265, 330])
    no_helmet = Detection(class_name="no_helmet", confidence=0.26, bbox=[145, 55, 255, 130])
    no_vest = Detection(class_name="no_vest", confidence=0.26, bbox=[135, 180, 265, 330])
    engine = SafetyRuleEngine(
        confirmation_frames=1,
        cooldown_seconds=10,
        ppe_grace_frames=2,
        ppe_warmup_frames=0,
    )

    # Both a positive and a conflicting negative can be returned by an
    # uncertain detector.  The positive association must take precedence.
    assert engine.evaluate_frame([worker, helmet, vest, no_helmet, no_vest], timestamp=base) == []
    # The same rule applies when the positive boxes briefly disappear: the
    # recent confirmed state remains valid during the grace interval.
    assert engine.evaluate_frame([worker, no_helmet, no_vest], timestamp=base + timedelta(seconds=1)) == []


def test_explicit_negative_class_reports_without_prior_ppe_evidence():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    worker = person(track_id=11)
    no_helmet = Detection(class_name="no_helmet", confidence=0.8, bbox=[145, 55, 255, 130])
    no_vest = Detection(class_name="no_vest", confidence=0.8, bbox=[135, 180, 265, 330])
    engine = SafetyRuleEngine(confirmation_frames=1, cooldown_seconds=10)

    events = engine.evaluate_frame([worker, no_helmet, no_vest], timestamp=base)
    assert {event.event_type for event in events} == {EventType.NO_HELMET, EventType.NO_VEST}


def test_danger_zone_intrusion_uses_bottom_center():
    zone = DangerZone(id="z1", polygon=[{"x": 80, "y": 400}, {"x": 320, "y": 400}, {"x": 320, "y": 480}, {"x": 80, "y": 480}])
    engine = SafetyRuleEngine(zones=[zone], confirmation_frames=1)
    events = engine.evaluate_frame([person(track_id=2)], timestamp=datetime.now(timezone.utc))
    assert any(event.event_type == EventType.INTRUSION and event.zone_id == "z1" for event in events)


def test_scale_zones_to_frame_resolves_relative_polygons():
    relative = DangerZone(
        id="r",
        coordinate_space="relative",
        polygon=[{"x": 0.5, "y": 0.5}, {"x": 0.25, "y": 0.75}, {"x": 0.75, "y": 0.75}],
    )
    pixel = DangerZone(id="p", polygon=[{"x": 10, "y": 20}, {"x": 30, "y": 40}, {"x": 50, "y": 60}])

    scaled = scale_zones_to_frame([relative, pixel], 640, 360)

    assert [(point.x, point.y) for point in scaled[0].polygon] == [(320.0, 180.0), (160.0, 270.0), (480.0, 270.0)]
    assert [(point.x, point.y) for point in scaled[1].polygon] == [(10.0, 20.0), (30.0, 40.0), (50.0, 60.0)]


def test_relative_zone_rules_match_across_resolutions():
    """One relative zone must fire on both a 640x360 and a 1920x1080 frame."""

    zone_data = [{"x": 0.1, "y": 0.7}, {"x": 0.9, "y": 0.7}, {"x": 0.9, "y": 1.0}, {"x": 0.1, "y": 1.0}]
    for width, height in ((640, 360), (1920, 1080)):
        zone = DangerZone(id=f"z-{width}", coordinate_space="relative", polygon=zone_data)
        engine = SafetyRuleEngine(zones=scale_zones_to_frame([zone], width, height), confirmation_frames=1)
        # A person standing at the frame's bottom centre is inside the zone.
        worker = Detection(
            class_name="person",
            confidence=0.95,
            bbox=BoundingBox(x1=width * 0.4, y1=height * 0.2, x2=width * 0.6, y2=height * 0.9),
            track_id=1,
        )
        events = engine.evaluate_frame([worker], timestamp=datetime.now(timezone.utc))
        assert any(event.event_type == EventType.INTRUSION for event in events)
