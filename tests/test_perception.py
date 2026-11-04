from datetime import UTC, datetime

import pytest

from rosa_turbopi.robot.camera.source import Frame
from rosa_turbopi.robot.perception.classes import DEFAULT_CLASSES
from rosa_turbopi.robot.perception.detector import YoloeDetector
from rosa_turbopi.robot.perception.errors import InferenceError
from rosa_turbopi.robot.perception.models import Detection, DetectionResult, horizontal_position

WIDTH, HEIGHT = 300, 200
DATA = b"encoded-image-bytes"


class Row(list):
    def tolist(self):
        return list(self)


class FakeBox:
    def __init__(self, xyxy, cls, conf):
        self.xyxy, self.cls, self.conf = [Row(xyxy)], [cls], [conf]


class FakeResults:
    def __init__(self, boxes):
        self.boxes = boxes


class FakeModel:
    """Stands in for YOLOE: records class changes and returns the queued boxes."""

    def __init__(self):
        self.names = {}
        self.boxes = []
        self.set_calls = []
        self.fail_set = False
        self.fail_predict = False

    def get_text_pe(self, names):
        return f"pe:{len(names)}"

    def set_classes(self, names, pe):
        if self.fail_set:
            raise RuntimeError("set_classes failed")
        self.set_calls.append(list(names))
        self.names = dict(enumerate(names))

    def __call__(self, image, verbose=False):
        if self.fail_predict:
            raise RuntimeError("model crashed")
        self.last_image = image
        return [FakeResults(self.boxes)]


def make_frame(frame_id="frame-1", data=DATA):
    return Frame(id=frame_id, captured_at=datetime.now(UTC), data=data, media_type="image/jpeg")


@pytest.fixture
def model():
    return FakeModel()


@pytest.fixture
def loads():
    return []


@pytest.fixture
def detector(model, loads):
    def load_model(path):
        loads.append(path)
        return model

    return YoloeDetector(
        "fake.pt",
        load_model=load_model,
        decode_image=lambda data: (("image", data), WIDTH, HEIGHT),
    )


@pytest.mark.parametrize(
    ("x_center", "expected"),
    [
        (0, "left"),
        (99.9, "left"),
        (100, "center"),
        (150, "center"),
        (200, "center"),
        (200.1, "right"),
        (300, "right"),
    ],
)
def test_horizontal_position_thirds(x_center, expected):
    assert horizontal_position(x_center, 300) == expected


def test_result_matches_the_frame_and_the_original_image_coordinates(detector, model):
    model.boxes = [FakeBox([10, 20, 90, 120], 0, 0.87), FakeBox([220, 30, 280, 100], 1, 0.5)]
    result = detector.detect(make_frame("abc"), ["red ball", "person"])
    assert result == DetectionResult(
        frame_id="abc",
        width=WIDTH,
        height=HEIGHT,
        detections=(
            Detection("red ball", 0.87, (10.0, 20.0, 90.0, 120.0), "left"),
            Detection("person", 0.5, (220.0, 30.0, 280.0, 100.0), "right"),
        ),
    )
    assert isinstance(result.detections, tuple)


def test_boxes_are_clamped_to_the_image_and_confidence_to_0_1(detector, model):
    model.boxes = [FakeBox([-5, -5, 320, 210], 0, 1.2)]
    (detection,) = detector.detect(make_frame(), ["person"]).detections
    assert detection.bbox == (0.0, 0.0, float(WIDTH), float(HEIGHT))
    assert detection.confidence == 1.0


def test_no_detections_is_a_normal_result(detector):
    result = detector.detect(make_frame("empty"), ["red ball"])
    assert result.detections == ()
    assert result.frame_id == "empty"


def test_named_classes_are_used_alone_without_defaults(detector, model):
    detector.detect(make_frame(), ["red ball"])
    assert model.set_calls == [["red ball"]]


@pytest.mark.parametrize("empty", [None, [], ["", "  "]])
def test_missing_or_empty_classes_use_the_defaults(detector, model, empty):
    detector.detect(make_frame(), empty)
    assert model.set_calls == [list(DEFAULT_CLASSES)]


def test_search_classes_do_not_depend_on_the_previous_call(detector, model):
    detector.detect(make_frame(), ["red ball"])
    detector.detect(make_frame(), None)
    detector.detect(make_frame(), ["person"])
    assert model.set_calls == [["red ball"], list(DEFAULT_CLASSES), ["person"]]


def test_classes_are_only_reapplied_when_they_change(detector, model):
    detector.detect(make_frame(), ["red ball", "red ball"])
    detector.detect(make_frame(), ["red ball"])
    assert model.set_calls == [["red ball"]]


def test_model_is_loaded_once_and_reused(detector, loads):
    for _ in range(3):
        detector.detect(make_frame(), ["red ball"])
    assert loads == ["fake.pt"]


def test_input_frame_is_not_modified(detector, model):
    frame = make_frame("keep", DATA)
    before = (frame.id, frame.captured_at, frame.data, frame.media_type)
    detector.detect(frame, ["red ball"])
    assert (frame.id, frame.captured_at, frame.data, frame.media_type) == before
    assert model.last_image == ("image", DATA)


def test_model_failure_raises_inference_error(detector, model):
    model.fail_predict = True
    with pytest.raises(InferenceError, match="model crashed"):
        detector.detect(make_frame(), ["red ball"])


def test_model_load_failure_raises_inference_error_and_can_be_retried():
    attempts = []

    def load_model(path):
        attempts.append(path)
        raise FileNotFoundError(path)

    detector = YoloeDetector("missing.pt", load_model=load_model, decode_image=lambda d: (d, 1, 1))
    for _ in range(2):
        with pytest.raises(InferenceError):
            detector.detect(make_frame(), None)
    assert attempts == ["missing.pt", "missing.pt"]


def test_decode_failure_raises_inference_error(model):
    def decode(data):
        raise InferenceError("Could not decode the image data")

    detector = YoloeDetector("fake.pt", load_model=lambda p: model, decode_image=decode)
    with pytest.raises(InferenceError, match="decode"):
        detector.detect(make_frame(), ["red ball"])


def test_failed_class_change_is_retried_on_the_next_call(detector, model):
    detector.detect(make_frame(), ["person"])
    model.fail_set = True
    with pytest.raises(InferenceError):
        detector.detect(make_frame(), ["red ball"])
    model.fail_set = False
    detector.detect(make_frame(), ["person"])
    assert model.set_calls == [["person"], ["person"]]


def test_missing_ultralytics_is_an_inference_error_with_install_hint(monkeypatch):
    import sys

    from rosa_turbopi.robot.perception.detector import load_yoloe

    monkeypatch.setitem(sys.modules, "ultralytics", None)
    with pytest.raises(InferenceError, match="uv sync --group vision"):
        load_yoloe("weights/x.pt")


def test_missing_opencv_is_an_inference_error_with_install_hint(monkeypatch):
    import sys

    from rosa_turbopi.robot.perception.detector import decode_with_cv2

    monkeypatch.setitem(sys.modules, "cv2", None)
    with pytest.raises(InferenceError, match="uv sync --group vision"):
        decode_with_cv2(b"x")
