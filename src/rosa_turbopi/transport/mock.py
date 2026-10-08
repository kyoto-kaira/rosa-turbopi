"""In-memory robot transport. No sockets, ROS or vendor SDKs."""

import json
from copy import deepcopy
from threading import Lock


class MockTransport:
    is_mock = True

    def __init__(self, echo: bool = False):
        self.connected = False
        self.commands = []
        self.echo = echo
        self._lock = Lock()

    def connect(self, timeout: float = 5) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def read_once(self, name: str, message_type: str, timeout: float) -> dict:
        if not self.connected:
            raise ConnectionError("mock is disconnected")
        return {"data": 7400}

    def publish_velocity(self, message: dict) -> None:
        if not self.connected:
            raise ConnectionError("mock is disconnected")
        with self._lock:
            self.commands.append(deepcopy(message))
            if self.echo:
                print("[MOCK /cmd_vel] " + json.dumps(message), flush=True)
