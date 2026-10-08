"""Load local connection and model settings."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    secure: bool
    battery_topic: str
    battery_type: str
    timeout_s: float
    model: str
    backend: str = "rosbridge"
    enable_motion: bool = True
    agent_max_iterations: int = 15
    agent_verbose: bool = False

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        port = int(os.getenv("ROSBRIDGE_PORT", "9090"))
        timeout = float(os.getenv("ROSBRIDGE_TIMEOUT_S", "5"))
        if not 1 <= port <= 65535 or not 0 < timeout <= 60:
            raise ValueError(
                "Invalid port or timeout (timeout must be 0–60 seconds, exclusive of 0)"
            )
        secure = os.getenv("ROSBRIDGE_SECURE", "false").lower()
        if secure not in {"true", "false"}:
            raise ValueError("ROSBRIDGE_SECURE must be true or false")
        backend = os.getenv("ROBOT_BACKEND", "rosbridge")
        if backend not in {"mock", "rosbridge"}:
            raise ValueError("ROBOT_BACKEND must be mock or rosbridge")
        enable_motion = os.getenv("ENABLE_MOTION", "true").lower()
        if enable_motion not in {"true", "false"}:
            raise ValueError("ENABLE_MOTION must be true or false")
        iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "15"))
        if not 1 <= iterations <= 50:
            raise ValueError("AGENT_MAX_ITERATIONS must be between 1 and 50")
        verbose = os.getenv("AGENT_VERBOSE", "false").lower()
        if verbose not in {"true", "false"}:
            raise ValueError("AGENT_VERBOSE must be true or false")
        return cls(
            host=os.getenv("ROSBRIDGE_HOST", "127.0.0.1"),
            port=port,
            secure=secure == "true",
            battery_topic="/ros_robot_controller/battery",
            battery_type="std_msgs/msg/UInt16",
            timeout_s=timeout,
            model=os.getenv("LLM_MODEL", ""),
            backend=backend,
            enable_motion=enable_motion == "true",
            agent_max_iterations=iterations,
            agent_verbose=verbose == "true",
        )
