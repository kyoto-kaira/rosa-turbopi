"""Adapt ROSA to an explicit rosbridge-only tool set."""

import os

from langchain_openai import ChatOpenAI
from rosa import ROSA, RobotSystemPrompts

from rosa_turbopi.prompts import SYSTEM_PROMPT
from rosa_turbopi.robot.client import TurboPiClient
from rosa_turbopi.tools.motion import build_tools as build_motion_tools
from rosa_turbopi.tools.status import build_tools


class BridgeTools:
    def __init__(self, tools: list):
        self._tools = tools

    def get_tools(self) -> list:
        return self._tools


class RosbridgeROSA(ROSA):
    """Skip ROSA's default CLI/system tools and their rclpy dependency.

    ROSA 1.0.10 calls this hook from its constructor. Keep the dependency pinned
    and test the hook when upgrading; blacklist is not a tool allowlist.
    """

    def _get_tools(self, ros_version, packages, tools, blacklist):
        return BridgeTools(tools or [])


def build_agent(robot: TurboPiClient) -> ROSA:
    if not robot.settings.model or not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Set LLM_MODEL and OPENAI_API_KEY for chat")
    llm = ChatOpenAI(model=robot.settings.model, temperature=0)
    return RosbridgeROSA(
        ros_version=2,
        llm=llm,
        tools=build_tools(robot) + build_motion_tools(robot),
        prompts=RobotSystemPrompts(embodiment_and_persona=SYSTEM_PROMPT),
        streaming=False,
        max_iterations=5,
    )
