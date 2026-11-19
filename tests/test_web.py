from threading import Event

from fastapi.testclient import TestClient
from langchain_core.tools import tool

from rosa_turbopi.robot.camera.source import CaptureError
from rosa_turbopi.settings import Settings
from rosa_turbopi.web.app import create_app


def settings():
    return Settings(
        "localhost",
        9090,
        False,
        "/battery",
        "std_msgs/UInt16",
        1,
        "",
        backend="mock",
        enable_motion=False,
    )


def test_camera_and_real_tool_events():
    def factory(robot, observe):
        @tool
        def battery() -> dict:
            """Read mock battery."""
            return robot.battery()

        tracked = observe(battery)

        class Agent:
            def invoke(self, query):
                tracked.invoke({})
                return "<script>alert(1)</script>"

        return Agent()

    with TestClient(create_app(settings(), factory)) as client:
        assert 'aria-label="ロボットバックエンド">mock' in client.get("/").text
        frame = client.get("/camera")
        assert frame.status_code == 200
        assert frame.headers["x-frame-id"]
        assert b"<svg" in frame.content
        client.post("/chat", data={"query": "電池を確認"})
        service = client.app.state.service
        service.worker.join(3)
        run = service.snapshot()[0]
        assert run.state == "completed"
        assert run.calls[0]["result"]["raw_value"] == 7400
        assert run.calls[0]["state"] == "completed"
        html = client.get("/runs/" + run.id).text
        assert "&lt;script&gt;" in html
        assert "<script>alert" not in html


def test_camera_capture_failure_is_reported_as_unavailable():
    class UnreachableCamera:
        def capture(self):
            raise CaptureError("Could not fetch a snapshot")

    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        client.app.state.robot.camera = UnreachableCamera()
        response = client.get("/camera")
        assert response.status_code == 503
        assert "Could not fetch a snapshot" in response.text
        assert response.headers["cache-control"] == "no-store"
        assert "x-frame-id" not in response.headers


def test_stop_blocks_later_tools_and_duplicate_submission():
    entered, resume = Event(), Event()

    def factory(robot, observe):
        @tool
        def move() -> dict:
            """Start motion."""
            robot.motion.start(0.5, 0, 0, 0.1)
            return robot.motion.join()

        tracked = observe(move)

        class Agent:
            def invoke(self, query):
                entered.set()
                resume.wait(3)
                return tracked.invoke({})

        return Agent()

    with TestClient(create_app(settings(), factory)) as client:
        client.post("/chat", data={"query": "前進"})
        assert entered.wait(3)
        client.post("/chat", data={"query": "重複"})
        assert len(client.app.state.service.snapshot()) == 1
        assert client.post("/stop").status_code == 200
        resume.set()
        client.app.state.service.worker.join(3)
        run = client.app.state.service.snapshot()[0]
        assert run.state == "cancelled"
        assert run.calls == []
        assert client.app.state.robot.motion.status()["state"] == "idle"


def test_stop_during_motion_records_cancelled_tool():
    from time import monotonic, sleep

    def factory(robot, observe):
        from rosa_turbopi.tools.motion import build_tools

        forward = observe(next(t for t in build_tools(robot) if t.name == "move_forward"))

        class Agent:
            def invoke(self, query):
                return forward.invoke({"duration_s": 3})

        return Agent()

    with TestClient(create_app(settings(), factory)) as client:
        client.post("/chat", data={"query": "3秒前進"})
        robot = client.app.state.robot
        deadline = monotonic() + 2
        while robot.motion.status()["state"] != "running" and monotonic() < deadline:
            sleep(0.01)
        assert robot.motion.status()["state"] == "running"
        client.post("/stop")
        service = client.app.state.service
        service.worker.join(3)
        run = service.snapshot()[0]
        assert run.state == "cancelled"
        assert run.calls[0]["state"] == "cancelled"


def test_reset_discards_agent_memory_and_history_but_keeps_robot():
    agents = []

    def factory(robot, observe):
        class Agent:
            def __init__(self):
                self.history = []

            def invoke(self, query):
                self.history.append(query)
                return str(len(self.history))

        agent = Agent()
        agents.append(agent)
        return agent

    with TestClient(create_app(settings(), factory)) as client:
        robot = client.app.state.robot
        service = client.app.state.service
        client.post("/chat", data={"query": "最初の会話"})
        service.worker.join(3)
        client.post("/chat", data={"query": "続き"})
        service.worker.join(3)
        assert service.snapshot()[-1].reply == "2"
        response = client.post("/conversation/reset")
        assert response.headers["HX-Trigger"] == "conversationReset"
        assert service.snapshot() == []
        assert service.agent is None
        assert "最初の会話" not in response.text
        assert client.app.state.robot is robot
        assert robot.transport.connected
        assert client.get("/camera").status_code == 200
        client.post("/chat", data={"query": "新しい会話"})
        service.worker.join(3)
        assert len(agents) == 2
        assert service.snapshot()[-1].reply == "1"


def test_reset_is_rejected_while_agent_is_running():
    entered, resume = Event(), Event()

    def factory(robot, observe):
        class Agent:
            def invoke(self, query):
                entered.set()
                resume.wait(3)
                return "完了"

        return Agent()

    with TestClient(create_app(settings(), factory)) as client:
        service = client.app.state.service
        client.post("/chat", data={"query": "処理中の会話"})
        assert entered.wait(3)
        try:
            response = client.post("/conversation/reset")
            assert "HX-Trigger" not in response.headers
            assert "実行中は会話をリセットできません" in response.text
            assert len(service.snapshot()) == 1
            assert 'id="reset-conversation"' in response.text
            assert 'hx-target="#workspace" disabled><svg class="reset-icon"' in response.text
        finally:
            resume.set()
            service.worker.join(3)


def test_tool_catalog_matches_agent_registry_without_llm(monkeypatch):
    from rosa_turbopi.tools.catalog import build_tools

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app(settings())) as client:
        response = client.get("/tools")
        assert response.status_code == 200
        assert "前進する" in response.text
        assert "状態確認" in response.text
        assert "duration_s" in response.text
        assert "必須" in response.text
        assert "任意" in response.text
        assert "0.5" in response.text
        robot = client.app.state.robot
        for registered in build_tools(robot):
            assert registered.name in response.text
        assert client.app.state.service.agent is None
        assert client.app.state.service.snapshot() == []
        assert robot.motion.status()["state"] == "idle"
        # Match a robot whose motion tools are unavailable.
        monkeypatch.setattr(robot.motion, "_enabled", False)
        response = client.get("/tools")
        assert "get_battery" in response.text
        assert "move_forward" not in response.text
        assert {t.name for t in build_tools(robot)} == {
            "get_connection_status",
            "get_battery",
            "detect_objects",
        }


def test_mock_hides_camera_and_does_not_open_stream():
    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        html = client.get("/").text
        assert "実機未接続" in html
        assert 'id="camera-stream"' not in html
        assert "<img" not in html
        assert client.get("/camera/stream").status_code == 204


def test_real_camera_stream_is_proxied_and_closed():
    from dataclasses import replace

    import httpx

    closed = []
    payload = b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg\r\n--frame--\r\n"

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield payload

        async def aclose(self):
            closed.append(True)

    def upstream(request):
        assert request.url.host == "localhost"
        assert request.url.port == 8080
        assert request.url.path == "/stream"
        # web_video_server does not decode %2F in the ROS topic query.
        assert b"topic=/image_raw" in request.url.query
        assert request.url.params["topic"] == "/image_raw"
        assert request.url.params["type"] == "mjpeg"
        return httpx.Response(
            200,
            headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame"},
            stream=Stream(),
        )

    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        client.app.state.robot.settings = replace(settings(), backend="rosbridge")
        client.app.state.robot.status = lambda: {"backend": "rosbridge", "connected": True}
        html = client.get("/").text
        assert 'id="camera-stream"' in html
        assert '<section class="camera panel"><h2>01 / CAMERA</h2>' in html
        assert "camera-live-view" not in html
        assert "camera-live-tab" not in html
        assert "camera-detection-frame" not in html
        original = client.app.state.camera_http
        client.app.state.camera_http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            response = client.get("/camera/stream")
            assert response.status_code == 200
            assert response.content == payload
            assert response.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"
            assert response.headers["cache-control"] == "no-store"
            assert closed
        finally:
            client.portal.call(client.app.state.camera_http.aclose)
            client.app.state.camera_http = original


def test_camera_stream_rejects_invalid_upstream_and_connection_errors():
    from dataclasses import replace

    import httpx

    def unavailable(request):
        raise httpx.ConnectError("offline", request=request)

    handlers = [
        lambda request: httpx.Response(200, text="not a stream"),
        lambda request: httpx.Response(502),
        unavailable,
    ]
    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        client.app.state.robot.settings = replace(settings(), backend="rosbridge")
        original = client.app.state.camera_http
        for handler in handlers:
            client.app.state.camera_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                assert client.get("/camera/stream").status_code == 503
            finally:
                client.portal.call(client.app.state.camera_http.aclose)
        client.app.state.camera_http = original


def test_only_running_tool_exposes_timestamp_for_browser_timer():
    from rosa_turbopi.execution.store import Run

    call = {
        "id": "call-1",
        "name": "detect_objects",
        "state": "running",
        "arguments": {},
        "result": "",
        "elapsed": 0,
        "started_at": "2026-11-16T00:00:00+00:00",
    }
    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        service = client.app.state.service
        service.runs.append(Run(query="何が見える？", calls=[call]))
        html = client.get("/").text
        assert 'data-started-at="2026-11-16T00:00:00+00:00"' in html
        call.update(state="completed", elapsed=12.34)
        html = client.get("/").text
        assert "data-started-at=" not in html
        assert "12.34s</span>" in html


def test_detection_view_and_details_share_original_image_and_boxes():
    from datetime import UTC, datetime

    from rosa_turbopi.execution.store import Run
    from rosa_turbopi.robot.camera.source import Frame
    from rosa_turbopi.robot.perception.models import Detection, DetectionResult
    from rosa_turbopi.tools.vision import completed

    frame = Frame("test-frame", datetime.now(UTC), b"original-jpeg", "image/jpeg")
    result = DetectionResult(
        frame.id,
        640,
        480,
        (
            Detection("<unsafe>", 0.85, (10, 20, 100, 200), "left"),
            Detection("<unsafe>", 0.90, (200, 20, 300, 200), "center"),
        ),
    )
    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        robot = client.app.state.robot
        robot.detection_frames.add(frame, result)
        service = client.app.state.service
        service.runs.append(
            Run(
                query="検出",
                state="completed",
                calls=[
                    {
                        "id": "call-test",
                        "name": "detect_objects",
                        "state": "completed",
                        "arguments": {},
                        "result": completed(result),
                        "elapsed": 1.2,
                    }
                ],
            )
        )
        html = client.get("/").text
        assert 'src="/detections/test-frame?thumbnail=true"' in html
        assert html.count('src="/detections/test-frame') == 1
        assert 'class="tool-detection-frame"' not in html
        assert 'class="detection-thumbnail"' in html
        assert 'class="expand-detection"' not in html
        assert html.index('class="detection-thumbnail"') < html.index("<details>")
        assert 'id="detection-dialog"' not in html
        assert "camera-live-tab" not in html
        assert "camera-detection-view" not in html
        assert "カメラ欄で表示" not in html
        view = client.get("/detections/test-frame")
        assert view.status_code == 200
        assert 'viewBox="0 0 640 480"' in view.text
        assert 'href="/detections/test-frame/image"' in view.text
        assert 'width="90" height="180"' in view.text
        assert "&lt;unsafe&gt;" in view.text
        assert "<unsafe>" not in view.text
        assert "85%" in view.text
        import re

        colors = re.findall(r"--bbox-color: (#[0-9a-f]+)", view.text)
        assert len(colors) == 2
        assert colors[0] != colors[1]
        thumbnail = client.get("/detections/test-frame?thumbnail=true")
        assert re.findall(r"--bbox-color: (#[0-9a-f]+)", thumbnail.text) == colors
        image = client.get("/detections/test-frame/image")
        assert image.content == b"original-jpeg"
        assert image.headers["content-type"] == "image/jpeg"
        assert client.post("/conversation/reset").status_code == 200
        assert client.get("/detections/test-frame/image").status_code == 404
        missing = client.get("/detections/test-frame")
        assert missing.status_code == 404
        assert "表示できません" in missing.text


def test_empty_detection_still_displays_captured_image():
    from datetime import UTC, datetime

    from rosa_turbopi.robot.camera.source import Frame
    from rosa_turbopi.robot.perception.models import DetectionResult

    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        frame = Frame("empty-frame", datetime.now(UTC), b"jpeg", "image/jpeg")
        client.app.state.robot.detection_frames.add(frame, DetectionResult(frame.id, 320, 240, ()))
        response = client.get("/detections/empty-frame")
        assert response.status_code == 200
        assert "検出なし" in response.text
        assert "/detections/empty-frame/image" in response.text


def test_timeline_history_navigation():
    import re

    from rosa_turbopi.execution.store import Run

    with TestClient(create_app(settings(), lambda robot, observe: None)) as client:
        runs = [Run(query=f"指示{i}", state="completed") for i in range(3)]
        client.app.state.service.runs.extend(runs)

        def buttons(path):
            html = client.get(path).text
            nav = re.search(r'<nav class="timeline-history".*?</nav>', html, re.DOTALL).group()
            assert f'data-latest-run-id="{runs[-1].id}"' in nav
            return re.findall(r"<button.*?</button>", nav, re.DOTALL)

        previous, following, latest = buttons("/")
        assert f"/runs/{runs[1].id}" in previous
        assert "disabled" in following and "disabled" in latest
        previous, following, latest = buttons(f"/runs/{runs[1].id}")
        assert f"/runs/{runs[0].id}" in previous
        assert f"/runs/{runs[2].id}" in following and f"/runs/{runs[2].id}" in latest
        previous, following, latest = buttons(f"/runs/{runs[0].id}")
        assert "disabled" in previous
        assert f"/runs/{runs[1].id}" in following
        client.app.state.service.runs.clear()
        html = client.get("/").text
        nav = re.search(r'<nav class="timeline-history".*?</nav>', html, re.DOTALL).group()
        assert nav.count("disabled") == 3
