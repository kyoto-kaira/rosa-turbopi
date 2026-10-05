from types import SimpleNamespace

import pytest

from rosa_turbopi.robot.client import TurboPiClient


class FakeTransport:
    connected = True

    def read_once(self, name, message_type, timeout):
        self.request = (name, message_type, timeout)
        return {"data": 12345}


def test_battery_preserves_raw_value_and_configured_interface():
    transport = FakeTransport()
    settings = SimpleNamespace(battery_topic="/battery", battery_type="custom/Value", timeout_s=2)
    robot = TurboPiClient(transport, settings)
    assert robot.battery() == {"raw_value": 12345, "unit": "unverified"}
    assert transport.request == ("/battery", "custom/Value", 2)
    assert robot.status()["movement_enabled"] is False


def test_battery_failure_is_not_reported_as_success():
    class FailingTransport(FakeTransport):
        def read_once(self, *args):
            raise TimeoutError("no battery")

    settings = SimpleNamespace(battery_topic="/battery", battery_type="custom/Value", timeout_s=2)
    with pytest.raises(TimeoutError):
        TurboPiClient(FailingTransport(), settings).battery()
