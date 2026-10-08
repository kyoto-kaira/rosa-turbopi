"""Real-backend paths tested entirely with a fake rosbridge connection."""

import pytest

from rosa_turbopi.robot.motion import MotionExecutor, twist
from rosa_turbopi.transport.rosbridge import RosbridgeClient


@pytest.fixture
def bridge(monkeypatch):
    class FakeRos:
        is_connected = True

        def __init__(self, **kwargs):
            pass

    class FakeTopic:
        def __init__(self, ros, name, message_type, **kwargs):
            assert name == "/cmd_vel"
            assert message_type == "geometry_msgs/msg/Twist"
            assert kwargs["reconnect_on_close"] is False
            self.messages = []

        def advertise(self):
            pass

        def publish(self, message):
            self.messages.append(dict(message))

    monkeypatch.setattr("rosa_turbopi.transport.rosbridge.roslibpy.Ros", FakeRos)
    monkeypatch.setattr("rosa_turbopi.transport.rosbridge.roslibpy.Topic", FakeTopic)
    return RosbridgeClient("unused", 9090, enable_motion=True)


def test_opt_in_real_path_sends_twist_and_final_stop(bridge):
    motion = MotionExecutor(bridge)
    assert motion.enabled and not motion.simulated
    result = motion.start(0.5, 0, 0, 0.01)
    assert result["simulated"] is False
    assert motion.join()["state"] == "completed"
    assert bridge._velocity.messages == [twist(0.5), twist()]


def test_default_real_backend_cannot_publish(bridge):
    bridge.motion_enabled = False
    assert not MotionExecutor(bridge).enabled
    with pytest.raises(PermissionError):
        bridge.publish_velocity(twist(0.5))
    assert bridge._velocity is None


def test_disconnect_prevents_publication(bridge):
    bridge._ros.is_connected = False
    with pytest.raises(ConnectionError):
        bridge.publish_velocity(twist(0.5))
    assert bridge._velocity is None


def test_stop_without_local_movement_sends_zero(bridge):
    motion = MotionExecutor(bridge)
    assert motion.stop()["simulated"] is False
    assert bridge._velocity.messages == [twist()]
