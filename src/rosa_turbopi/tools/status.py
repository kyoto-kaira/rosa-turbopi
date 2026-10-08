"""Explicitly allowed, read-only LangChain tools."""

from langchain_core.tools import tool

from rosa_turbopi.robot.client import TurboPiClient


def build_tools(robot: TurboPiClient) -> list:
    @tool
    def get_connection_status() -> dict:
        """接続状態・backend・movement_enabled・移動状態を確認する。

        操作前に一度確認する。完了した操作の確認を繰り返さない。
        移動状態は指令処理の状態であり、センサーの実測ではない。"""
        return robot.status()

    @tool
    def get_battery() -> dict:
        """バッテリーの生値を読む。単位は未確認なので電圧や残量へ換算しない。"""
        return robot.battery()

    return [get_connection_status, get_battery]
