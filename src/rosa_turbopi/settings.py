"""Load local connection and model settings."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
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

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        path = Path(os.getenv("TURBOPI_CONFIG", "config/turbopi.example.yaml"))
        config = yaml.safe_load(path.read_text())
        battery = config["battery"]
        port = int(os.getenv("ROSBRIDGE_PORT", "9090"))
        timeout = float(battery.get("timeout_s", 5))
        if not 1 <= port <= 65535 or not 0 < timeout <= 60:
            raise ValueError(
                "Invalid port or timeout (timeout must be 0–60 seconds, exclusive of 0)"
            )
        secure = os.getenv("ROSBRIDGE_SECURE", "false").lower()
        if secure not in {"true", "false"}:
            raise ValueError("ROSBRIDGE_SECURE must be true or false")
        return cls(
            host=os.getenv("ROSBRIDGE_HOST", "127.0.0.1"),
            port=port,
            secure=secure == "true",
            battery_topic=battery["topic"],
            battery_type=battery["message_type"],
            timeout_s=timeout,
            model=os.getenv("LLM_MODEL", ""),
        )
