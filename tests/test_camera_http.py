import threading
import time
from datetime import UTC, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from rosa_turbopi.robot.camera.http import HttpSnapshotCamera
from rosa_turbopi.robot.camera.source import CaptureError
from rosa_turbopi.settings import Settings

JPEG = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


class Handler(BaseHTTPRequestHandler):
    mode = "ok"
    requested: ClassVar[list[str]] = []

    def do_GET(self):
        type(self).requested.append(self.path)
        mode = type(self).mode
        if mode == "slow":
            time.sleep(1)
        status = 500 if mode == "error" else 200
        body = b"" if mode == "empty" else (b"<html>" if mode == "html" else JPEG)
        ctype = "text/html" if mode == "html" else "image/jpeg"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass  # the client already timed out

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    Handler.mode = "ok"
    Handler.requested = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def camera_for(port: int, timeout_s: float = 2.0) -> HttpSnapshotCamera:
    return HttpSnapshotCamera(
        Settings(
            "127.0.0.1",
            9090,
            False,
            "/battery",
            "std_msgs/UInt16",
            1,
            "",
            camera_port=port,
            camera_topic="/image_raw",
            camera_timeout_s=timeout_s,
        )
    )


def test_capture_returns_frame_for_the_configured_topic(server):
    frame = camera_for(server.server_port).capture()
    assert frame.data == JPEG
    assert frame.media_type == "image/jpeg"
    assert Handler.requested == ["/snapshot?topic=/image_raw"]


def test_frame_ids_are_unique_and_captured_at_is_utc(server):
    camera = camera_for(server.server_port)
    first, second = camera.capture(), camera.capture()
    assert first.id != second.id
    assert first.captured_at.utcoffset() == timedelta(0)
    assert first.captured_at.tzinfo is UTC
    assert first.captured_at <= second.captured_at


@pytest.mark.parametrize("mode", ["error", "empty", "html"])
def test_bad_responses_raise_capture_error(server, mode):
    Handler.mode = mode
    with pytest.raises(CaptureError):
        camera_for(server.server_port).capture()


def test_timeout_raises_capture_error(server):
    Handler.mode = "slow"
    with pytest.raises(CaptureError):
        camera_for(server.server_port, timeout_s=0.2).capture()


def test_unreachable_robot_raises_capture_error(server):
    port = server.server_port
    server.shutdown()
    server.server_close()
    with pytest.raises(CaptureError):
        camera_for(port).capture()
