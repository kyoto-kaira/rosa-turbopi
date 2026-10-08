from rosa_turbopi.settings import Settings


def test_motion_enabled_by_default_and_can_be_disabled(monkeypatch):
    # Never load the user's local secrets or create a robot connection.
    monkeypatch.setattr("rosa_turbopi.settings.load_dotenv", lambda: None)
    monkeypatch.delenv("ENABLE_MOTION", raising=False)
    assert Settings.load().enable_motion is True
    monkeypatch.setenv("ENABLE_MOTION", "false")
    assert Settings.load().enable_motion is False


import pytest


@pytest.mark.parametrize("value", ["0", "-1", "61", "nan", "inf"])
def test_invalid_timeout_is_rejected(monkeypatch, value):
    monkeypatch.setattr("rosa_turbopi.settings.load_dotenv", lambda: None)
    monkeypatch.setenv("ROSBRIDGE_TIMEOUT_S", value)
    with pytest.raises(ValueError):
        Settings.load()


def test_timeout_from_environment_and_fixed_interface(monkeypatch, tmp_path):
    monkeypatch.setattr("rosa_turbopi.settings.load_dotenv", lambda: None)
    monkeypatch.setenv("ROSBRIDGE_TIMEOUT_S", "2.5")
    monkeypatch.chdir(tmp_path)
    settings = Settings.load()
    assert settings.timeout_s == 2.5
    assert settings.battery_topic == "/ros_robot_controller/battery"
    assert settings.battery_type == "std_msgs/msg/UInt16"
