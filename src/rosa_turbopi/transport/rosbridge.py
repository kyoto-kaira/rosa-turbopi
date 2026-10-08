"""rosbridge transport with explicitly enabled velocity publication."""

from threading import Event

import roslibpy


class RosbridgeClient:
    def __init__(self, host: str, port: int, secure: bool = False, enable_motion: bool = False):
        self._ros = roslibpy.Ros(host=host, port=port, is_secure=secure)
        self.motion_enabled = enable_motion
        self._velocity = None
        self._started = False

    @property
    def connected(self) -> bool:
        return self._ros.is_connected

    def connect(self, timeout: float = 5) -> None:
        self._started = True
        self._ros.run(timeout=timeout)

    def close(self) -> None:
        if self._velocity is not None and self.connected:
            self._velocity.unadvertise()
        if self._started:
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

    def publish_velocity(self, message: dict) -> None:
        if not self.motion_enabled:
            raise PermissionError("Set ENABLE_MOTION=true to enable real velocity publication")
        if not self.connected:
            raise ConnectionError("rosbridge disconnected; velocity was not sent")
        if self._velocity is None:
            self._velocity = roslibpy.Topic(
                self._ros, "/cmd_vel", "geometry_msgs/msg/Twist", reconnect_on_close=False
            )
            self._velocity.advertise()
        self._velocity.publish(roslibpy.Message(message))
