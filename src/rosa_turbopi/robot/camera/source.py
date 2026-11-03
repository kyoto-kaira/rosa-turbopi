"""Camera frames shared by browser and future perception tools."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Frame:
    id: str
    captured_at: datetime
    data: bytes
    media_type: str


class CameraSource(Protocol):
    def capture(self) -> Frame: ...
