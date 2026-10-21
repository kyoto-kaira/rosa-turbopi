from threading import Event

from fastapi.testclient import TestClient
from langchain_core.tools import tool

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
        assert "MOCK CAMERA" in client.get("/").text
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
