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
