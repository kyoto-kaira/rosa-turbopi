"""CLI entry point. Read-only commands never require an LLM key."""

import argparse
import json
import sys

from rosa_turbopi.robot.client import TurboPiClient
from rosa_turbopi.settings import Settings
from rosa_turbopi.transport.mock import MockTransport
from rosa_turbopi.transport.rosbridge import RosbridgeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="ROSA → TurboPi (real read-only / mock motion)")
    parser.add_argument("command", choices=["check", "battery", "chat", "move", "stop"])
    parser.add_argument("--vx", type=float, default=0)
    parser.add_argument("--vy", type=float, default=0)
    parser.add_argument("--wz", type=float, default=0)
    parser.add_argument("--duration", type=float, default=1)
    args = parser.parse_args()
    transport = None
    robot = None
    try:
        settings = Settings.load()
        if args.command in {"move", "stop"} and settings.backend != "mock":
            raise PermissionError("Real movement is disabled; use ROBOT_BACKEND=mock")
        transport = (
            MockTransport(echo=True)
            if settings.backend == "mock"
            else RosbridgeClient(settings.host, settings.port, settings.secure)
        )
        robot = TurboPiClient(transport, settings)
        agent = None
        if args.command == "chat":
            from rosa_turbopi.agent import build_agent

            agent = build_agent(robot)
        transport.connect(timeout=settings.timeout_s)
        if args.command == "check":
            print(json.dumps(robot.status(), ensure_ascii=False))
        elif args.command == "battery":
            print(json.dumps(robot.battery(), ensure_ascii=False))
        elif args.command == "move":
            print(json.dumps(robot.motion.start(args.vx, args.vy, args.wz, args.duration)))
            result = robot.motion.join()
            print(json.dumps(result))
            if result["error"]:
                raise RuntimeError(result["error"])
        elif args.command == "stop":
            print(json.dumps(robot.motion.stop()))
        else:
            print(f"バックエンド: {settings.backend}（実機走行は無効）")
            print("日本語で入力してください。/stop はLLMを使わず模擬停止、/quit で終了。")
            while True:
                query = input("> ").strip()
                if query == "/quit":
                    break
                if query == "/stop":
                    if robot.motion.enabled:
                        print(robot.motion.stop())
                    else:
                        print("実機の停止指令は無効です。")
                    continue
                if query:
                    print(agent.invoke(query))
    except (KeyboardInterrupt, EOFError):
        pass
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        try:
            if robot is not None:
                robot.motion.close()
        finally:
            if transport is not None:
                transport.close()
