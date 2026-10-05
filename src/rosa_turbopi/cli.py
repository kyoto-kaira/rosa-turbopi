"""CLI entry point. Read-only commands never require an LLM key."""

import argparse
import json
import sys

from rosa_turbopi.robot.client import TurboPiClient
from rosa_turbopi.settings import Settings
from rosa_turbopi.transport.rosbridge import RosbridgeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="ROSA → rosbridge → TurboPi (read-only scaffold)")
    parser.add_argument("command", choices=["check", "battery", "chat"])
    args = parser.parse_args()
    transport = None
    try:
        settings = Settings.load()
        transport = RosbridgeClient(settings.host, settings.port, settings.secure)
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
        else:
            print("日本語で入力してください。/quit で終了します（走行は未実装）。")
            while True:
                query = input("> ").strip()
                if query == "/quit":
                    break
                if query:
                    print(agent.invoke(query))
    except (KeyboardInterrupt, EOFError):
        pass
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        if transport is not None:
            transport.close()
