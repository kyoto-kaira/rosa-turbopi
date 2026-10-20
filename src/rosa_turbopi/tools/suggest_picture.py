"""Vision tools: camera snapshot object detection (optional: uv sync --group vision).カメラ検出（detect_objects）は画像1枚の確認だけで、移動はしない。
見つけた物体へ近づく場合は、検出結果を報告し、移動の方向と時間をユーザーに確認してから移動ツールを使う。"""

import os
import urllib.request

from langchain_core.tools import tool

from rosa_turbopi.robot.client import TurboPiClient

DEFAULT_MODEL_PATH = "weights/yolov8s-worldv2.pt"
SNAPSHOT_PORT = 8080


def build_tools(robot: TurboPiClient) -> list:
    timeout = float(os.getenv("ROSBRIDGE_TIMEOUT_S", "5"))
    host = os.getenv("ROSBRIDGE_HOST", "localhost")
    url = f"http://{host}:{SNAPSHOT_PORT}/snapshot?topic=/image_raw"
    model_path = os.getenv("YOLOE_MODEL", DEFAULT_MODEL_PATH)
    model = None  # 初回の検出時に読み込む（CLI起動を重くしない）

    def horizontal(x_center: float, width: int) -> str:
        if x_center < width / 3:
            return "left"
        if x_center > width * 2 / 3:
            return "right"
        return "center"

    @tool
    def detect_objects(target_classes: list[str] | None = None) -> dict:
        """カメラの現在の画像を1枚取得し、物体検出を行う。移動はしない。

        target_classesは探したい物体の英語名のリスト。例: ["person", "bottle", "red car"]。
        指定がなければ前回設定したクラスを使う。クラスは検出のたびに更新される。
        初回は日本語の指示を英語に直して渡す。
        戻り値は state（completed=検出処理完了、failed=失敗）と、
        image（width, height）、detections（空なら見つからなかった）。
        各検出は class、confidence（0〜1）、bbox（[x1, y1, x2, y2]、左上が原点のピクセル座標）、
        horizontal（left / center / right、画像を3分割した位置）。
        距離は分からない。1枚の画像による結果で、見えなかっただけの可能性もある。"""
        nonlocal model
        if robot.motion.simulated:
            return {
                "state": "failed",
                "error": "モックではカメラを使えません",
                "simulated": True,
            }
        try:
            import cv2
            import numpy as np
            from ultralytics import YOLOE

            if model is None:
                model = YOLOE(model_path)
            if target_classes:
                model.set_classes(target_classes)

            with urllib.request.urlopen(url, timeout=timeout) as res:
                data = res.read()
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                return {"state": "failed", "error": "画像をデコードできませんでした"}

            height, width = frame.shape[:2]
            results = model(frame, verbose=False)
            detections = []
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    {
                        "class": model.names[int(box.cls[0])],
                        "confidence": round(float(box.conf[0]), 2),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "horizontal": horizontal((x1 + x2) / 2, width),
                    }
                )
            return {
                "state": "completed",
                "image": {"width": width, "height": height},
                "detections": detections,
                "simulated": False,
            }
        except ImportError:
            return {"state": "failed", "error": "uv sync --group vision が必要です"}
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            return {"state": "failed", "error": str(exc), "simulated": False}

    return [detect_objects]
