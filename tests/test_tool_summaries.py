from rosa_turbopi.web.summaries import tool_summary


def test_detection_summary_counts_objects_and_empty_result():
    call = {
        "name": "detect_objects",
        "state": "completed",
        "result": {
            "state": "completed",
            "detections": [{"label": "person"}, {"label": "person"}, {"label": "bottle"}],
        },
    }
    assert tool_summary(call) == "検出3件：person ×2、bottle ×1"
    call["result"]["detections"] = []
    assert tool_summary(call) == "検出なし"


def test_motion_summary_does_not_claim_success_for_cancelled_or_failed_calls():
    call = {
        "name": "move_forward",
        "state": "completed",
        "arguments": {"duration_s": 1},
        "result": {"state": "completed"},
    }
    assert tool_summary(call) == "前進 1秒の指令完了"
    call["result"] = {"state": "cancelled"}
    assert tool_summary(call) == "取消"
    call["result"] = {"state": "failed", "error": "接続切れ"}
    assert tool_summary(call) == "失敗：接続切れ"
    call["state"] = "running"
    assert tool_summary(call) == ""
