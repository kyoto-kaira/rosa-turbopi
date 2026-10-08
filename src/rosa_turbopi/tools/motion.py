"""Motion tools for mock or explicitly enabled real transport."""

import math

from langchain_core.tools import tool

from rosa_turbopi.robot.client import TurboPiClient


def build_tools(robot: TurboPiClient) -> list:
    if not robot.motion.enabled:
        return []

    @tool
    def move_for(vx: float, vy: float, wz: float, duration_s: float) -> dict:
        """速度成分を指定して移動する。単独の移動・回転には方向別ツールを優先する。

        vxは前進、vyは左横移動（m/s）、wzは左回転（rad/s）。負値は逆方向。
        並進合成速度は0または0.4〜0.9、角速度の絶対値は最大7.0。
        duration_sは必須で0より大きく最大3秒。不明なら確認する。距離・角度指定は非対応。
        終了時のゼロ速度送信まで待ち、completed（指令処理完了）、cancelled（取消）、
        failed（失敗）、rejected（拒否）を返す。実測の移動・停止を保証しない。"""
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
        """前進する。

        duration_sは必須で0より大きく最大3秒。不明なら確認する。
        speedは正のm/sで0.4〜0.9、既定0.5。ゆっくり=0.4、標準=0.5、速く=0.9。
        終了時のゼロ速度送信まで待ち、completed（指令処理完了）、cancelled（取消）、
        failed（失敗）、rejected（拒否）を返す。距離指定は非対応。実測の移動・停止を保証しない。"""
        return directional(speed, duration_s, "vx", 1)

    @tool
    def move_backward(duration_s: float, speed: float = 0.5) -> dict:
        """後退する。

        duration_sは必須で0より大きく最大3秒。不明なら確認する。
        speedは正のm/sで0.4〜0.9、既定0.5。ゆっくり=0.4、標準=0.5、速く=0.9。
        終了時のゼロ速度送信まで待ち、completed（指令処理完了）、cancelled（取消）、
        failed（失敗）、rejected（拒否）を返す。距離指定は非対応。実測の移動・停止を保証しない。"""
        return directional(speed, duration_s, "vx", -1)

    @tool
    def move_left(duration_s: float, speed: float = 0.5) -> dict:
        """向きを変えず左へ横移動する。

        duration_sは必須で0より大きく最大3秒。不明なら確認する。
        speedは正のm/sで0.4〜0.9、既定0.5。ゆっくり=0.4、標準=0.5、速く=0.9。
        終了時のゼロ速度送信まで待ち、completed（指令処理完了）、cancelled（取消）、
        failed（失敗）、rejected（拒否）を返す。距離指定は非対応。実測の移動・停止を保証しない。"""
        return directional(speed, duration_s, "vy", 1)

    @tool
    def move_right(duration_s: float, speed: float = 0.5) -> dict:
        """向きを変えず右へ横移動する。

        duration_sは必須で0より大きく最大3秒。不明なら確認する。
        speedは正のm/sで0.4〜0.9、既定0.5。ゆっくり=0.4、標準=0.5、速く=0.9。
        終了時のゼロ速度送信まで待ち、completed（指令処理完了）、cancelled（取消）、
        failed（失敗）、rejected（拒否）を返す。距離指定は非対応。実測の移動・停止を保証しない。"""
        return directional(speed, duration_s, "vy", -1)

    @tool
    def rotate_left(duration_s: float, angular_speed: float = 5.0) -> dict:
        """その場で左（反時計回り）へ回転する。

        duration_sは必須で0より大きく最大3秒。不明なら確認する。
        angular_speedは正のrad/sで最大7.0、既定5.0。
        終了時のゼロ速度送信まで待ち、completed（指令処理完了）、cancelled（取消）、
        failed（失敗）、rejected（拒否）を返す。角度指定は非対応。実測の回転・停止を保証しない。"""
        return directional(angular_speed, duration_s, "wz", 1)

    @tool
    def rotate_right(duration_s: float, angular_speed: float = 5.0) -> dict:
        """その場で右（時計回り）へ回転する。

        duration_sは必須で0より大きく最大3秒。不明なら確認する。
        angular_speedは正のrad/sで最大7.0、既定5.0。
        終了時のゼロ速度送信まで待ち、completed（指令処理完了）、cancelled（取消）、
        failed（失敗）、rejected（拒否）を返す。角度指定は非対応。実測の回転・停止を保証しない。"""
        return directional(angular_speed, duration_s, "wz", -1)

    @tool
    def stop() -> dict:
        """実行中の移動を取り消し、ゼロ速度を送る。

        停止指令の送信結果と現在の状態を返す。失敗時はfailedと理由を返す。
        物理的な停止をセンサーで確認する操作ではない。"""
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
