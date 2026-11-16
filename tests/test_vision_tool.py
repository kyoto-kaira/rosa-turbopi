import json
from datetime import UTC, datetime
from types import SimpleNamespace

from rosa_turbopi.robot.camera.source import CaptureError, Frame
from rosa_turbopi.robot.perception.errors import InferenceError
from rosa_turbopi.robot.perception.models import Detection, DetectionResult
from rosa_turbopi.tools.vision import build_tools, shared_detector

FRAME = Frame(
    id="frame-9",
    captured_at=datetime.now(UTC),
    data=b"\xff\xd8secret-image-bytes",
    media_type="image/jpeg",
)


class FakeCamera:
    def __init__(self, error=None):
        self.error = error
        self.captures = 0

    def capture(self):
        self.captures += 1
        if self.error:
            raise self.error
        return FRAME


class FakeDetector:
    def __init__(self, detections=(), error=None):
        self.detections = tuple(detections)
        self.error = error
        self.calls = []

    def detect(self, frame, target_classes=None):
        self.calls.append((frame, target_classes))
        if self.error:
            raise self.error
        return DetectionResult(frame.id, 640, 480, self.detections)


def make_tool(camera=None, detector=None, simulated=False):
    robot = SimpleNamespace(motion=SimpleNamespace(simulated=simulated), camera=camera)
    (tool,) = build_tools(robot, detector)
    return tool


def test_completed_result_is_json_with_frame_id_size_and_detections():
    detector = FakeDetector(
        [Detection("red ball", 0.8123, (10.04, 20.0, 90.0, 120.26), "left")],
    )
    result = make_tool(FakeCamera(), detector).invoke({"target_classes": ["red ball"]})
    assert result == {
        "state": "completed",
        "frame_id": "frame-9",
        "image": {"width": 640, "height": 480},
        "detections": [
            {
                "label": "red ball",
                "confidence": 0.81,
                "bbox": [10.0, 20.0, 90.0, 120.3],
                "horizontal": "left",
            }
        ],
        "simulated": False,
    }
    text = json.dumps(result)
    assert "secret-image-bytes" not in text
    assert "data" not in result


def test_tool_passes_the_captured_frame_and_classes_to_the_detector():
    detector = FakeDetector()
    make_tool(FakeCamera(), detector).invoke({"target_classes": ["red ball", "person"]})
    assert detector.calls == [(FRAME, ["red ball", "person"])]


def test_classes_are_optional():
    detector = FakeDetector()
    tool = make_tool(FakeCamera(), detector)
    tool.invoke({})
    tool.invoke({"target_classes": ["person"]})
    tool.invoke({})
    assert [classes for _, classes in detector.calls] == [None, ["person"], None]


def test_no_detections_is_completed_not_failed():
    result = make_tool(FakeCamera(), FakeDetector()).invoke({})
    assert result["state"] == "completed"
    assert result["detections"] == []


def test_capture_failure_is_reported_and_skips_detection():
    detector = FakeDetector()
    camera = FakeCamera(CaptureError("Could not fetch a snapshot"))
    result = make_tool(camera, detector).invoke({"target_classes": ["person"]})
    assert result == {
        "state": "failed",
        "stage": "capture",
        "error": "Could not fetch a snapshot",
        "simulated": False,
    }
    assert detector.calls == []


def test_inference_failure_is_reported_with_the_frame_id():
    detector = FakeDetector(error=InferenceError("model crashed"))
    result = make_tool(FakeCamera(), detector).invoke({"target_classes": ["person"]})
    assert result == {
        "state": "failed",
        "stage": "inference",
        "error": "model crashed",
        "frame_id": "frame-9",
        "simulated": False,
    }


def test_capture_and_inference_failures_can_be_told_apart():
    capture = make_tool(FakeCamera(CaptureError("x")), FakeDetector()).invoke({})
    inference = make_tool(FakeCamera(), FakeDetector(error=InferenceError("x"))).invoke({})
    assert capture["state"] == inference["state"] == "failed"
    assert (capture["stage"], inference["stage"]) == ("capture", "inference")


def test_mock_backend_does_not_touch_camera_or_detector():
    camera, detector = FakeCamera(), FakeDetector()
    result = make_tool(camera, detector, simulated=True).invoke({})
    assert result["state"] == "failed"
    assert result["simulated"] is True
    assert camera.captures == 0
    assert detector.calls == []


def test_shared_detector_is_reused_and_does_not_load_the_model():
    shared_detector.cache_clear()
    first = shared_detector("weights/a.pt")
    assert shared_detector("weights/a.pt") is first
    assert first._model is None
    shared_detector.cache_clear()


def test_building_tools_does_not_need_the_vision_dependencies():
    robot = SimpleNamespace(motion=SimpleNamespace(simulated=False), camera=FakeCamera())
    (tool,) = build_tools(robot)
    assert tool.name == "detect_objects"
    assert "前回" in tool.description  # states that nothing is carried over between calls
