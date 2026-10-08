"""All movement tests use in-memory transports, never the robot network."""

from threading import Event

import pytest

from rosa_turbopi.robot.motion import MotionExecutor, twist
from rosa_turbopi.tools.motion import build_tools
from rosa_turbopi.transport.mock import MockTransport


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def wait(self, duration):
        self.now += duration


def setup_motion():
    transport = MockTransport()
    transport.connect()
    clock = Clock()
    return transport, MotionExecutor(transport, clock=clock, wait=clock.wait)


def test_duration_ends_with_zero_velocity():
    transport, motion = setup_motion()
    motion.start(0.05, 0, 0, 0.25)
    assert motion.join()["state"] == "completed"
    assert transport.commands[:-1] == [twist(0.05)] * 3
    assert transport.commands[-1] == twist()


@pytest.mark.parametrize(
    "args",
    [
        (0.11, 0, 0, 1),
        (0.08, 0.08, 0, 1),
        (0, 0, 0.31, 1),
        (0, 0, 0, 0),
        (0, 0, 0, 4),
        (float("nan"), 0, 0, 1),
        (0, 0, float("inf"), 1),
        (True, 0, 0, 1),
    ],
)
def test_invalid_commands_never_publish(args):
    transport, motion = setup_motion()
    with pytest.raises(ValueError):
        motion.start(*args)
    assert not transport.commands


def test_stop_cancels_and_rejects_overlap():
    transport = MockTransport()
    transport.connect()
    entered = Event()
    motion = MotionExecutor(transport)

    def wait(duration):
        entered.set()
        motion._cancel.wait(2)

    motion._wait = wait
    motion.start(0, -0.05, -0.1, 3)
    assert entered.wait(1)
    with pytest.raises(RuntimeError):
        motion.start(0.05, 0, 0, 1)
    assert motion.stop()["state"] == "cancelled"
    assert transport.commands[0] == twist(0, -0.05, -0.1)
    assert all(command == twist() for command in transport.commands[1:])


def test_failure_attempts_stop_and_reports_failure(monkeypatch):
    transport, motion = setup_motion()
    attempted = []

    def fail(message):
        attempted.append(message)
        raise ConnectionError("disconnected")

    monkeypatch.setattr(transport, "publish_velocity", fail)
    motion.start(0.05, 0, 0, 1)
    result = motion.join()
    assert result["state"] == "failed"
    assert "Stop delivery failed" in result["error"]
    assert attempted == [twist(0.05), twist()]


def test_real_transport_is_blocked_even_if_it_has_publish_method():
    class RealTransport:
        connected = True

        def publish_velocity(self, message):
            pytest.fail("Real transport must never publish")

    motion = MotionExecutor(RealTransport())
    with pytest.raises(PermissionError):
        motion.start(0.05, 0, 0, 1)
    with pytest.raises(PermissionError):
        motion.stop()
    robot = type("Robot", (), {"motion": motion})()
    assert build_tools(robot) == []


def test_disconnected_mock_never_starts():
    transport, motion = setup_motion()
    transport.close()
    with pytest.raises(ConnectionError):
        motion.start(0.05, 0, 0, 1)
    assert not transport.commands


def test_motion_tool_returns_rejection_and_simulation_label():
    transport, motion = setup_motion()
    robot = type("Robot", (), {"motion": motion})()
    tools = build_tools(robot)
    result = tools[0].invoke({"vx": 1, "vy": 0, "wz": 0, "duration_s": 1})
    assert result["state"] == "rejected"
    assert result["simulated"] is True
    assert not transport.commands


@pytest.mark.parametrize(
    "name, expected",
    [
        ("move_forward", twist(0.05)),
        ("move_backward", twist(-0.05)),
        ("move_left", twist(0, 0.05)),
        ("move_right", twist(0, -0.05)),
        ("rotate_left", twist(0, 0, 0.1)),
        ("rotate_right", twist(0, 0, -0.1)),
    ],
)
def test_directional_tools_publish_correct_axis_then_stop(name, expected):
    transport, motion = setup_motion()
    robot = type("Robot", (), {"motion": motion})()
    tools = {t.name: t for t in build_tools(robot)}
    result = tools[name].invoke({"duration_s": 0.1})
    assert result["state"] == "started"
    assert result["simulated"] is True
    assert motion.join()["state"] == "completed"
    assert transport.commands == [expected, twist()]


@pytest.mark.parametrize(
    "name, speed_key",
    [
        ("move_forward", "speed"),
        ("move_backward", "speed"),
        ("move_left", "speed"),
        ("move_right", "speed"),
        ("rotate_left", "angular_speed"),
        ("rotate_right", "angular_speed"),
    ],
)
@pytest.mark.parametrize("speed", [-0.05, 0, float("nan"), float("inf"), 0.4])
def test_directional_tools_reject_invalid_speed_without_publish(name, speed_key, speed):
    transport, motion = setup_motion()
    robot = type("Robot", (), {"motion": motion})()
    tools = {t.name: t for t in build_tools(robot)}
    result = tools[name].invoke({"duration_s": 1, speed_key: speed})
    assert result["state"] == "rejected"
    assert not transport.commands
