"""YOLOE object detection on a Frame. Never touches the camera."""

import threading
from collections.abc import Callable, Sequence
from typing import Any

from rosa_turbopi.robot.camera.source import Frame
from rosa_turbopi.robot.perception.classes import DEFAULT_CLASSES
from rosa_turbopi.robot.perception.errors import InferenceError
from rosa_turbopi.robot.perception.models import Detection, DetectionResult, horizontal_position

DEFAULT_MODEL_PATH = "weights/yoloe-26s-seg.pt"

# A decoder turns encoded image bytes into (image for the model, width, height).
Decoder = Callable[[bytes], tuple[Any, int, int]]


def load_yoloe(model_path: str) -> Any:
    try:
        from ultralytics import YOLOE
    except ImportError as exc:
        raise InferenceError("ultralytics is not installed (uv sync --group vision)") from exc
    return YOLOE(model_path)


def decode_with_cv2(data: bytes) -> tuple[Any, int, int]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise InferenceError("opencv-python is not installed (uv sync --group vision)") from exc

    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise InferenceError("Could not decode the image data")
    height, width = image.shape[:2]
    return image, width, height


def _clean(target_classes: Sequence[str] | None) -> list[str]:
    names = [name.strip() for name in (target_classes or []) if name and name.strip()]
    return list(dict.fromkeys(names)) or list(DEFAULT_CLASSES)


class YoloeDetector:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        *,
        load_model: Callable[[str], Any] = load_yoloe,
        decode_image: Decoder = decode_with_cv2,
    ):
        self._model_path = model_path
        self._load_model = load_model
        self._decode_image = decode_image
        self._lock = threading.Lock()
        self._model: Any = None
        self._applied: list[str] | None = None

    def detect(self, frame: Frame, target_classes: Sequence[str] | None = None) -> DetectionResult:
        names = _clean(target_classes)
        with self._lock:
            try:
                image, width, height = self._decode_image(frame.data)
                model = self._ready_model(names)
                results = model(image, verbose=False)
                detections = tuple(
                    self._to_detection(model, box, width, height) for box in results[0].boxes
                )
            except InferenceError:
                raise
            except Exception as exc:
                raise InferenceError(f"{type(exc).__name__}: {exc}") from exc
        return DetectionResult(frame.id, width, height, detections)

    def _ready_model(self, names: list[str]) -> Any:
        if self._model is None:
            self._model = self._load_model(self._model_path)
        if self._applied != names:
            self._applied = None  # unknown until set_classes succeeds
            self._model.set_classes(names, self._model.get_text_pe(names))
            self._applied = names
        return self._model

    @staticmethod
    def _to_detection(model: Any, box: Any, width: int, height: int) -> Detection:
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
        x1, x2 = (min(max(v, 0.0), float(width)) for v in (x1, x2))
        y1, y2 = (min(max(v, 0.0), float(height)) for v in (y1, y2))
        return Detection(
            label=str(model.names[int(box.cls[0])]),
            confidence=min(max(float(box.conf[0]), 0.0), 1.0),
            bbox=(x1, y1, x2, y2),
            horizontal=horizontal_position((x1 + x2) / 2, width),
        )
