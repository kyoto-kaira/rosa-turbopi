"""Still-image capture from the robot's HTTP snapshot endpoint."""

import http.client
import urllib.request
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import uuid4

from rosa_turbopi.robot.camera.source import CaptureError, Frame
from rosa_turbopi.settings import Settings


class HttpSnapshotCamera:
    """CameraSource that fetches one JPEG per capture() call."""

    def __init__(self, settings: Settings):
        # Read settings at capture time so building a robot never needs camera values.
        self._settings = settings

    @property
    def url(self) -> str:
        settings = self._settings
        query = urlencode({"topic": settings.camera_topic}, safe="/")
        return f"http://{settings.host}:{settings.camera_port}/snapshot?{query}"

    def capture(self) -> Frame:
        url = self.url
        try:
            with urllib.request.urlopen(url, timeout=self._settings.camera_timeout_s) as response:
                captured_at = datetime.now(UTC)
                media_type = response.headers.get_content_type()
                data = response.read()
        except (OSError, http.client.HTTPException) as exc:
            raise CaptureError(f"Could not fetch a snapshot from {url}: {exc}") from exc
        if not media_type.startswith("image/"):
            raise CaptureError(f"Snapshot endpoint returned {media_type}, not an image")
        if not data:
            raise CaptureError("Snapshot endpoint returned an empty body")
        return Frame(id=uuid4().hex, captured_at=captured_at, data=data, media_type=media_type)
