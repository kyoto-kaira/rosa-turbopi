"""Vision tool: take one still image and look for objects (optional: uv sync --group vision)."""

import os
from functools import lru_cache

from langchain_core.tools import tool

from rosa_turbopi.robot.camera.source import CaptureError
from rosa_turbopi.robot.client import TurboPiClient
from rosa_turbopi.robot.perception.detector import DEFAULT_MODEL_PATH, YoloeDetector
from rosa_turbopi.robot.perception.errors import InferenceError
from rosa_turbopi.robot.perception.models import DetectionResult


@lru_cache(maxsize=1)
def shared_detector(model_path: str) -> YoloeDetector:
    """One detector per process, so the model is loaded once even when tools are rebuilt."""
    return YoloeDetector(model_path)


def completed(result: DetectionResult) -> dict:
    return {
        "state": "completed",
        "frame_id": result.frame_id,
        "image": {"width": result.width, "height": result.height},
        "detections": [
            {
                "label": d.label,
                "confidence": round(d.confidence, 2),
                "bbox": [round(v, 1) for v in d.bbox],
                "horizontal": d.horizontal,
            }
            for d in result.detections
        ],
        "simulated": False,
    }


def failed(stage: str, error: str, *, frame_id: str | None = None, simulated: bool = False):
    # state stays "failed" because the execution history only treats that value as a failure.
    result = {"state": "failed", "stage": stage, "error": error, "simulated": simulated}
    if frame_id is not None:
        result["frame_id"] = frame_id
    return result


def build_tools(robot: TurboPiClient, detector: YoloeDetector | None = None) -> list:
    def get_detector():
        # Resolved on first use so building the tools never loads the model.
        if detector is not None:
            return detector
        return shared_detector(os.getenv("YOLOE_MODEL", DEFAULT_MODEL_PATH))

    @tool
    def detect_objects(target_classes: list[str] | None = None) -> dict:
        """カメラの現在の画像を1枚撮影し、物体検出を行う。移動はしない。

        target_classesは探したい物体の英語名のリスト。例: ["red ball"]、["person", "bottle"]。
        日本語の指示は英語に直して渡す。指定した物体だけを探す。
        指定がない（または空）場合は、一般的な物体と色付きのボールを探す。
        呼び出しごとに独立しており、前回の指定は引き継がない。
        戻り値のstateは completed（検出処理完了）か failed（失敗）。
        completedなら frame_id、image（width, height）、detections（空なら見つからなかった）を含む。
        各検出は label、confidence（0〜1）、bbox（[x1, y1, x2, y2]、左上が原点のピクセル座標）、
        horizontal（left / center / right、画像を左右に3分割した位置）。
        failedなら stage が capture（撮影の失敗）か inference（検出の失敗）で、errorに理由が入る。
        距離は分からない。1枚の画像による結果で、見えなかっただけの可能性もある。
        見つけた物体へ近づく場合は、検出結果を報告し、移動の方向と時間を確認してから移動する。"""
        if robot.motion.simulated:
            return failed("capture", "モックではカメラ画像を使えません", simulated=True)
        try:
            frame = robot.camera.capture()
        except CaptureError as exc:
            return failed("capture", str(exc))
        try:
            result = get_detector().detect(frame, target_classes)
        except InferenceError as exc:
            return failed("inference", str(exc), frame_id=frame.id)
        return completed(result)

    return [detect_objects]
