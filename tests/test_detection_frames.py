from datetime import UTC, datetime

from rosa_turbopi.robot.camera.source import Frame
from rosa_turbopi.robot.perception.frames import DetectionFrames
from rosa_turbopi.robot.perception.models import DetectionResult


def add(store, frame_id, data=b"jpeg"):
    frame = Frame(frame_id, datetime.now(UTC), data, "image/jpeg")
    result = DetectionResult(frame_id, 640, 480, ())
    store.add(frame, result)
    return frame, result


def test_frames_retain_exact_detection_image_and_evict_oldest():
    store = DetectionFrames(max_frames=2)
    frame, result = add(store, "a")
    assert store.get("a").frame is frame
    assert store.get("a").result is result
    add(store, "b")
    add(store, "c")
    assert store.get("a") is None
    assert store.get("b") is not None
    assert store.get("c") is not None
    store.clear()
    assert store.get("c") is None


def test_byte_budget_includes_replacements_and_oversized_frames():
    store = DetectionFrames(max_bytes=8)
    add(store, "a", b"1234")
    add(store, "a", b"123456")
    add(store, "b", b"12")
    assert store.get("a") is not None
    add(store, "c", b"12")
    assert store.get("a") is None
    assert store.get("b") is not None
    add(store, "too-big", b"x" * 9)
    assert store.get("too-big") is None
