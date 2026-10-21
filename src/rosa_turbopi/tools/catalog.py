"""Single tool registry shared by ROSA and the console."""

from rosa_turbopi.tools.motion import build_tools as build_motion_tools
from rosa_turbopi.tools.status import build_tools as build_status_tools

TITLES = {
    "get_connection_status": "接続・動作状態を確認する",
    "get_battery": "バッテリーを確認する",
    "move_for": "速度を指定して移動する",
    "move_forward": "前進する",
    "move_backward": "後退する",
    "move_left": "左へ横移動する",
    "move_right": "右へ横移動する",
    "rotate_left": "左へ回転する",
    "rotate_right": "右へ回転する",
    "stop": "移動を停止する",
}


def tool_groups(robot):
    return [("状態確認", build_status_tools(robot)), ("移動", build_motion_tools(robot))]


def build_tools(robot):
    return [tool for _, tools in tool_groups(robot) for tool in tools]


def describe_tools(robot):
    groups = []
    for name, tools in tool_groups(robot):
        entries = []
        for tool in tools:
            schema = tool.get_input_schema().model_json_schema()
            required = schema.get("required", [])
            arguments = [
                {
                    "name": key,
                    "type": value.get("type", ""),
                    "required": key in required,
                    "default": value.get("default"),
                    "description": value.get("description", ""),
                }
                for key, value in schema.get("properties", {}).items()
            ]
            entries.append(
                {
                    "name": tool.name,
                    "title": TITLES.get(tool.name, tool.description.splitlines()[0]),
                    "description": tool.description,
                    "arguments": arguments,
                }
            )
        if entries:
            groups.append({"name": name, "tools": entries})
    return groups
