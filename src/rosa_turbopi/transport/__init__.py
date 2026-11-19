"""Construct the configured transport without opening a connection."""

from rosa_turbopi.settings import Settings
from rosa_turbopi.transport.mock import MockTransport
from rosa_turbopi.transport.rosbridge import RosbridgeClient


def create_transport(settings: Settings, echo: bool = False) -> MockTransport | RosbridgeClient:
    if settings.backend == "mock":
        return MockTransport(echo=echo)
    return RosbridgeClient(
        settings.host, settings.port, settings.secure, enable_motion=settings.enable_motion
    )
