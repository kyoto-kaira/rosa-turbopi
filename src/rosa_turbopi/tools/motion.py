"""Motion tools for mock or explicitly enabled real transport."""

import math

from langchain_core.tools import tool

from rosa_turbopi.robot.client import TurboPiClient


def build_tools(robot: TurboPiClient) -> list:
    if not robot.motion.enabled:
        return []

    @tool
    def move_for(vx: float, vy: float, wz: float, duration_s: float) -> dict:
        """移動を開始。vxは前進、vyは左、wzは左旋回。負値は逆方向。

        速度はm/sとrad/s。並進合成速度は停止の0または0.4〜0.9、旋回は最大7.0、時間は最大3秒。
        終了時のゼロ速度送信まで待ち、completed・cancelled・failedを返す。モックでは模擬操作、実機では指令送信。距離・角度指定は非対応。
        """
        try:
            robot.motion.start(vx, vy, wz, duration_s)
            return robot.motion.join()
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            return {"state": "rejected", "error": str(exc), "simulated": robot.motion.simulated}

    def directional(speed: float, duration_s: float, axis: str, sign: int) -> dict:
        if not math.isfinite(speed) or speed <= 0:
            return {
                "state": "rejected",
                "error": "Speed must be finite and positive",
                "simulated": robot.motion.simulated,
            }
        velocity = {"vx": 0.0, "vy": 0.0, "wz": 0.0}
        velocity[axis] = sign * speed
        try:
            robot.motion.start(**velocity, duration_s=duration_s)
            return robot.motion.join()
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            return {"state": "rejected", "error": str(exc), "simulated": robot.motion.simulated}

    @tool
    def move_forward(duration_s: float, speed: float = 0.5) -> dict:
        """選択したバックエンドで前進。時間は秒（最大3）、速度は正のm/s（0.4〜0.9）。モックでは模擬操作、実機では指令送信。"""
        return directional(speed, duration_s, "vx", 1)

    @tool
    def move_backward(duration_s: float, speed: float = 0.5) -> dict:
        """選択したバックエンドで後退。時間は秒（最大3）、速度は正のm/s（0.4〜0.9）。モックでは模擬操作、実機では指令送信。"""
        return directional(speed, duration_s, "vx", -1)

    @tool
    def move_left(duration_s: float, speed: float = 0.5) -> dict:
        """選択したバックエンドで向きを変えず左へ横移動。時間は秒（最大3）、正のm/s（0.4〜0.9）。"""
        return directional(speed, duration_s, "vy", 1)

    @tool
    def move_right(duration_s: float, speed: float = 0.5) -> dict:
        """選択したバックエンドで向きを変えず右へ横移動。時間は秒（最大3）、正のm/s（0.4〜0.9）。"""
        return directional(speed, duration_s, "vy", -1)

    @tool
    def rotate_left(duration_s: float, angular_speed: float = 5.0) -> dict:
        """選択したバックエンドでその場で左（反時計回り）回転。秒（最大3）、正のrad/s（最大7.0）。"""
        return directional(angular_speed, duration_s, "wz", 1)

    @tool
    def rotate_right(duration_s: float, angular_speed: float = 5.0) -> dict:
        """選択したバックエンドでその場で右（時計回り）回転。秒（最大3）、正のrad/s（最大7.0）。"""
        return directional(angular_speed, duration_s, "wz", -1)

    @tool
    def stop() -> dict:
        """移動を取り消しゼロ速度を送る。モックでは模擬操作、実機では指令送信。"""
        try:
            return robot.motion.stop()
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            return {"state": "failed", "error": str(exc), "simulated": robot.motion.simulated}

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
