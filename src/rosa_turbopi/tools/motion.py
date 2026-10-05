"""Motion tools exposed only for the in-memory backend."""

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

    @tool
    def stop() -> dict:
        """模擬移動を取り消しゼロ速度を送る。実機は動かない。"""
        try:
            return robot.motion.stop()
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            return {"state": "failed", "error": str(exc), "simulated": True}

    return [move_for, stop]
