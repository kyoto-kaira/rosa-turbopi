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
        assert {t.name for t in build_tools(robot)} == {"get_connection_status", "get_battery"}
