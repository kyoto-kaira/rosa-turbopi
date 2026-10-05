"""Explicitly allowed, read-only LangChain tools."""

from langchain_core.tools import tool

from rosa_turbopi.robot.client import TurboPiClient


def build_tools(robot: TurboPiClient) -> list:
    @tool
    def get_connection_status() -> dict:
        """接続状態と、走行操作が有効かどうかを確認する。"""
        return robot.status()

    @tool
    def get_battery() -> dict:
        """バッテリーの生値を読む。単位は未確認なので電圧や残量へ換算しない。"""
        return robot.battery()

    return [get_connection_status, get_battery]
