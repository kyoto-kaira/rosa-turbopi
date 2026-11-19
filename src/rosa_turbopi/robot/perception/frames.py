"""Bounded, process-local images for reviewing completed detections."""

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

from rosa_turbopi.robot.camera.source import Frame
from rosa_turbopi.robot.perception.models import DetectionResult


@dataclass(frozen=True)
class DetectionFrame:
    frame: Frame
    result: DetectionResult


class DetectionFrames:
    def __init__(self, max_frames=20, max_bytes=64 * 1024 * 1024):
        self.max_frames = max_frames
        self.max_bytes = max_bytes
        self._frames: OrderedDict[str, DetectionFrame] = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    def add(self, frame: Frame, result: DetectionResult):
        with self._lock:
            previous = self._frames.pop(frame.id, None)
            if previous:
                self._bytes -= len(previous.frame.data)
            self._frames[frame.id] = DetectionFrame(frame, result)
            self._bytes += len(frame.data)
            while self._frames and (
                len(self._frames) > self.max_frames or self._bytes > self.max_bytes
            ):
                _, removed = self._frames.popitem(last=False)
                self._bytes -= len(removed.frame.data)

    def get(self, frame_id: str) -> DetectionFrame | None:
        with self._lock:
            return self._frames.get(frame_id)

    def clear(self):
        with self._lock:
            self._frames.clear()
            self._bytes = 0
