"""Read-only rosbridge transport; does not require ROS or vendor SDKs."""

from threading import Event

import roslibpy


class RosbridgeClient:
    def __init__(self, host: str, port: int, secure: bool = False):
        self._ros = roslibpy.Ros(host=host, port=port, is_secure=secure)

    @property
    def connected(self) -> bool:
        return self._ros.is_connected

    def connect(self, timeout: float = 5) -> None:
        self._ros.run(timeout=timeout)

    def close(self) -> None:
        self._ros.terminate()

    def read_once(self, name: str, message_type: str, timeout: float) -> dict:
        if not self.connected:
            raise ConnectionError("rosbridge is disconnected")
        ready = Event()
        messages = []
        topic = roslibpy.Topic(self._ros, name, message_type)

        def receive(message):
            if not ready.is_set():
                messages.append(dict(message))
                ready.set()

        try:
            topic.subscribe(receive)
            if not ready.wait(timeout):
                raise TimeoutError(f"No message from {name} within {timeout} seconds")
            return messages[0]
        finally:
            topic.unsubscribe()
