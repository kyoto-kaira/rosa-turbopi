"""Bounded mock motion with cancellation and observable completion."""

import math
import time
from threading import Event, Lock, Thread

from rosa_turbopi.transport.mock import MockTransport


def twist(vx: float = 0, vy: float = 0, wz: float = 0) -> dict:
    return {"linear": {"x": vx, "y": vy, "z": 0}, "angular": {"x": 0, "y": 0, "z": wz}}


class MotionExecutor:
    MAX_LINEAR = 0.1
    MAX_ANGULAR = 0.3
    MAX_DURATION = 3.0
    PERIOD = 0.1

    def __init__(self, transport, clock=time.monotonic, wait=None):
        # No environment variable can enable real motion in this version.
        self._enabled = type(transport) is MockTransport
        self._transport = transport
        self._clock = clock
        self._cancel = Event()
        self._wait = wait if wait is not None else self._cancel.wait
        self._lock = Lock()
        self._stopping = False
        self._thread = None
        self._state = "idle"
        self._error = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def status(self) -> dict:
        with self._lock:
            return {"state": self._state, "error": self._error, "simulated": self._enabled}

    def start(self, vx: float, vy: float, wz: float, duration_s: float) -> dict:
        if not self._enabled:
            raise PermissionError("Real robot movement is disabled; use ROBOT_BACKEND=mock")
        values = (vx, vy, wz, duration_s)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
            raise ValueError("Motion arguments must be numbers")
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Motion arguments must be finite")
        if math.hypot(vx, vy) > self.MAX_LINEAR or abs(wz) > self.MAX_ANGULAR:
            raise ValueError("Speed exceeds limits: linear 0.1 m/s, angular 0.3 rad/s")
        if not 0 < duration_s <= self.MAX_DURATION:
            raise ValueError("Duration must be greater than 0 and at most 3 seconds")
        with self._lock:
            if self._stopping or (self._thread is not None and self._thread.is_alive()):
                raise RuntimeError("Movement already active; stop it first")
            if not self._transport.connected:
                raise ConnectionError("Transport is disconnected")
            self._cancel.clear()
            self._state = "running"
            self._error = None
            self._thread = Thread(
                target=self._run, args=(twist(vx, vy, wz), duration_s), daemon=True
            )
            self._thread.start()
        return {"state": "started", "simulated": True, "duration_s": duration_s}

    def _run(self, message: dict, duration_s: float) -> None:
        error = None
        try:
            deadline = self._clock() + duration_s
            while not self._cancel.is_set():
                remaining = deadline - self._clock()
                if remaining <= 0:
                    break
                self._transport.publish_velocity(message)
                self._wait(min(self.PERIOD, remaining))
        except Exception as exc:  # noqa: BLE001 - retain worker errors and attempt stop
            error = str(exc)
        finally:
            try:
                self._transport.publish_velocity(twist())
            except Exception as exc:  # noqa: BLE001 - retain worker errors and attempt stop
                error = f"{error or ''} Stop delivery failed: {exc}".strip()
            with self._lock:
                self._error = error
                self._state = (
                    "failed" if error else ("cancelled" if self._cancel.is_set() else "completed")
                )

    def stop(self) -> dict:
        if not self._enabled:
            raise PermissionError("Real robot stop commands are disabled in this version")
        with self._lock:
            self._stopping = True
            self._cancel.set()
            thread = self._thread
        try:
            if thread is not None:
                thread.join(timeout=2)
                if thread.is_alive():
                    raise TimeoutError("Movement worker did not stop")
            self._transport.publish_velocity(twist())
            result = self.status()
            if result["error"]:
                raise RuntimeError(result["error"])
            return result
        finally:
            with self._lock:
                self._stopping = False

    def join(self, timeout: float = 5) -> dict:
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise TimeoutError("Movement is still running")
        return self.status()

    def close(self) -> None:
        if self._enabled and self._thread is not None:
            self.stop()
