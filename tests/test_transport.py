import pytest

from rosa_turbopi.transport.rosbridge import RosbridgeClient


@pytest.mark.parametrize("deliver", [True, False])
def test_subscription_cleanup(monkeypatch, deliver):
    class FakeTopic:
        unsubscribed = False

        def __init__(self, *args):
            pass

        def subscribe(self, callback):
            if deliver:
                callback({"data": 42})

        def unsubscribe(self):
            FakeTopic.unsubscribed = True

    monkeypatch.setattr("rosa_turbopi.transport.rosbridge.roslibpy.Topic", FakeTopic)
    client = RosbridgeClient.__new__(RosbridgeClient)
    client._ros = type("FakeRos", (), {"is_connected": True})()
    if deliver:
        assert client.read_once("/battery", "std_msgs/msg/UInt16", 0.01) == {"data": 42}
    else:
        with pytest.raises(TimeoutError):
            client.read_once("/battery", "std_msgs/msg/UInt16", 0.01)
    assert FakeTopic.unsubscribed


def test_disconnected_read_fails_before_subscription():
    client = RosbridgeClient.__new__(RosbridgeClient)
    client._ros = type("FakeRos", (), {"is_connected": False})()
    with pytest.raises(ConnectionError):
        client.read_once("/battery", "std_msgs/msg/UInt16", 1)
