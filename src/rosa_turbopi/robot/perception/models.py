"""Detection types shared by the perception code and the web UI."""

from dataclasses import dataclass
from typing import Literal

Horizontal = Literal["left", "center", "right"]


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]
    horizontal: Horizontal


@dataclass(frozen=True)
class DetectionResult:
    frame_id: str
    width: int
    height: int
    detections: tuple[Detection, ...]


def horizontal_position(x_center: float, width: int) -> Horizontal:
    """Which third of the image a point falls in; the exact boundaries count as center."""
    if x_center < width / 3:
        return "left"
    if x_center > width * 2 / 3:
        return "right"
    return "center"
