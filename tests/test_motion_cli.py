import pytest

from rosa_turbopi.cli import main


def test_real_move_is_rejected_before_constructing_transport(monkeypatch, capsys):
    monkeypatch.setenv("ROBOT_BACKEND", "rosbridge")
    monkeypatch.setattr("sys.argv", ["rosa-turbopi", "move", "--vx", "0.05"])

    def forbidden(*args):
        pytest.fail("Real transport must not be created")

    monkeypatch.setattr("rosa_turbopi.cli.RosbridgeClient", forbidden)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "Real movement is disabled" in capsys.readouterr().err


def test_mock_move_runs_without_real_transport(monkeypatch, capsys):
    monkeypatch.setenv("ROBOT_BACKEND", "mock")
    monkeypatch.setattr("sys.argv", ["rosa-turbopi", "move", "--vx", "0.05", "--duration", "0.01"])

    def forbidden(*args):
        pytest.fail("Mock mode must not create a real transport")

    monkeypatch.setattr("rosa_turbopi.cli.RosbridgeClient", forbidden)
    main()
    assert '"state": "completed"' in capsys.readouterr().out


def test_chat_keeps_prompt_clear_and_accepts_next_command(monkeypatch, capsys):
    monkeypatch.setenv("ROBOT_BACKEND", "mock")
    monkeypatch.setattr("sys.argv", ["rosa-turbopi", "chat"])

    class Agent:
        def __init__(self, robot):
            self.robot = robot

        def invoke(self, query):
            self.robot.motion.start(0.05, 0, 0, 0.01)
            self.robot.motion.join()
            return "模擬前進しました"

    monkeypatch.setattr("rosa_turbopi.agent.build_agent", Agent)
    commands = iter(["前進して", "/status", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    main()
    output = capsys.readouterr().out
    assert "模擬前進しました" in output
    assert '"state": "completed"' in output
    assert "[MOCK /cmd_vel]" not in output
