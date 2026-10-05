"""Robot operations exposed to agent tools."""

from rosa_turbopi.settings import Settings
from rosa_turbopi.transport.rosbridge import RosbridgeClient


class TurboPiClient:
    def __init__(self, transport: RosbridgeClient, settings: Settings):
        self.transport = transport
        self.settings = settings

    def status(self) -> dict:
        return {"connected": self.transport.connected, "movement_enabled": False}

    def battery(self) -> dict:
        message = self.transport.read_once(
            self.settings.battery_topic,
            self.settings.battery_type,
            self.settings.timeout_s,
        )
        # Preserve the raw value until the vendor's unit convention is verified.
        return {"raw_value": message["data"], "unit": "unverified"}
