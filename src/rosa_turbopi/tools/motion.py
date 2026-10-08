"""Motion tools exposed only for the in-memory backend."""

import math

from langchain_core.tools import tool

from rosa_turbopi.robot.client import TurboPiClient


def build_tools(robot: TurboPiClient) -> list:
    if not robot.motion.enabled:
        return []

    @tool
    def move_for(vx: float, vy: float, wz: float, duration_s: float) -> dict:
        """模擬移動を開始。vxは前進、vyは左、wzは左旋回。負値は逆方向。

        速度はm/sとrad/s。並進合成速度は最大0.1、旋回は最大0.3、時間は最大3秒。
        開始後はバックグラウンド実行。実機は動かない。距離・角度指定は非対応。
        """
        try:
            return robot.motion.start(vx, vy, wz, duration_s)
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            return {"state": "rejected", "error": str(exc), "simulated": True}

    def directional(speed: float, duration_s: float, axis: str, sign: int) -> dict:
        if not math.isfinite(speed) or speed <= 0:
            return {
                "state": "rejected",
                "error": "Speed must be finite and positive",
                "simulated": True,
            }
        velocity = {"vx": 0.0, "vy": 0.0, "wz": 0.0}
        velocity[axis] = sign * speed
        try:
            return robot.motion.start(**velocity, duration_s=duration_s)
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            return {"state": "rejected", "error": str(exc), "simulated": True}

    @tool
    def move_forward(duration_s: float, speed: float = 0.05) -> dict:
        """モックで前進。時間は秒（最大3）、速度は正のm/s（最大0.1）。実機は動かない。"""
        return directional(speed, duration_s, "vx", 1)

    @tool
    def move_backward(duration_s: float, speed: float = 0.05) -> dict:
        """モックで後退。時間は秒（最大3）、速度は正のm/s（最大0.1）。実機は動かない。"""
        return directional(speed, duration_s, "vx", -1)

    @tool
    def move_left(duration_s: float, speed: float = 0.05) -> dict:
        """モックで向きを変えず左へ横移動。時間は秒（最大3）、正のm/s（最大0.1）。"""
        return directional(speed, duration_s, "vy", 1)

    @tool
    def move_right(duration_s: float, speed: float = 0.05) -> dict:
        """モックで向きを変えず右へ横移動。時間は秒（最大3）、正のm/s（最大0.1）。"""
        return directional(speed, duration_s, "vy", -1)

    @tool
    def rotate_left(duration_s: float, angular_speed: float = 0.1) -> dict:
        """モックでその場で左（反時計回り）回転。秒（最大3）、正のrad/s（最大0.3）。"""
        return directional(angular_speed, duration_s, "wz", 1)

    @tool
    def rotate_right(duration_s: float, angular_speed: float = 0.1) -> dict:
        """モックでその場で右（時計回り）回転。秒（最大3）、正のrad/s（最大0.3）。"""
        return directional(angular_speed, duration_s, "wz", -1)

    @tool
    def stop() -> dict:
        """模擬移動を取り消しゼロ速度を送る。実機は動かない。"""
        try:
            return robot.motion.stop()
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            return {"state": "failed", "error": str(exc), "simulated": True}

    return [
        move_for,
        stop,
        move_forward,
        move_backward,
        move_left,
        move_right,
        rotate_left,
        rotate_right,
    ]
