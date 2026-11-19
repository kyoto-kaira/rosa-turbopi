"""Short, deterministic UI summaries of tool results."""

from collections import Counter

MOTIONS = {
    "move_forward": "前進",
    "move_backward": "後退",
    "move_left": "左へ移動",
    "move_right": "右へ移動",
    "rotate_left": "左回転",
    "rotate_right": "右回転",
    "move_for": "移動",
}


def tool_summary(call):
    result = call.get("result")
    result = result if isinstance(result, dict) else {}
    state = result.get("state", call.get("state"))
    if call.get("state") == "running":
        return ""
    if state in {"failed", "rejected", "cancelled"}:
        label = {"failed": "失敗", "rejected": "拒否", "cancelled": "取消"}[state]
        reason = str(result.get("error") or "")
        return f"{label}：{reason[:120]}" if reason else label
    name = call.get("name")
    prefix = "モック · " if result.get("simulated") else ""
    if name == "detect_objects" and state == "completed":
        detections = result.get("detections", [])
        counts = Counter(d.get("label", "不明") for d in detections)
        if not counts:
            return "検出なし"
        labels = "、".join(f"{label} ×{count}" for label, count in list(counts.items())[:3])
        extra = f"、ほか{len(counts) - 3}種類" if len(counts) > 3 else ""
        return f"検出{len(detections)}件：{labels}{extra}"
    if name in MOTIONS and state == "completed":
        duration = (call.get("arguments") or {}).get("duration_s")
        seconds = f" {duration:g}秒" if isinstance(duration, (int, float)) else ""
        return f"{prefix}{MOTIONS[name]}{seconds}の指令完了"
    if name == "stop" and state in {"completed", "idle"}:
        return f"{prefix}停止指令を送信"
    if name == "get_connection_status" and "connected" in result:
        return "接続済み" if result["connected"] else "未接続"
    if name == "get_battery" and "raw_value" in result:
        return f"バッテリー値：{result['raw_value']}"
    return ""
