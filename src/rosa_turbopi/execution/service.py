"""One shared agent, with observable tools and cooperative cancellation."""

from copy import deepcopy
from functools import wraps
from threading import Event, RLock, Thread
from time import monotonic
from uuid import uuid4

from rosa_turbopi.execution.store import Run


class ExecutionService:
    def __init__(self, robot, factory=None):
        self.robot = robot
        self.factory = factory
        self.agent = None
        self.runs = []
        self.lock = RLock()
        self.cancelled = Event()
        self.worker = None
        self.closed = False

    def snapshot(self):
        with self.lock:
            return deepcopy(self.runs)

    def observe(self, tool):
        original = tool.func

        @wraps(original)
        def invoke(*args, **kwargs):
            if self.cancelled.is_set():
                raise RuntimeError("Execution cancelled")
            started = monotonic()
            call = {
                "id": uuid4().hex,
                "name": tool.name,
                "arguments": kwargs or args,
                "state": "running",
                "result": "",
                "elapsed": 0,
            }
            with self.lock:
                run = self.runs[-1]
                run.calls.append(call)
            try:
                result = original(*args, **kwargs)
                state = (
                    result.get("state", "completed") if isinstance(result, dict) else "completed"
                )
                if state not in {"failed", "rejected", "cancelled"}:
                    state = "completed"
                with self.lock:
                    call.update(state=state, result=result)
                return result
            except Exception as exc:
                with self.lock:
                    call.update(state="failed", result=str(exc))
                raise
            finally:
                with self.lock:
                    call["elapsed"] = round(monotonic() - started, 2)

        tool.func = invoke
        return tool

    def submit(self, query):
        with self.lock:
            if self.closed or (self.worker and self.worker.is_alive()):
                raise RuntimeError("実行中の指示が完了するまでお待ちください。")
            self.cancelled.clear()
            self.robot.motion.block(False)
            run = Run(query=query)
            self.runs.append(run)
            self.worker = Thread(target=self._execute, args=(run,), daemon=True)
            self.worker.start()
            return run.id

    def _execute(self, run):
        try:
            if self.agent is None:
                from rosa_turbopi.agent import build_agent

                self.agent = (self.factory or build_agent)(self.robot, observe=self.observe)
            reply = self.agent.invoke(run.query)
            with self.lock:
                run.reply = str(reply)
                run.state = "failed" if run.reply.startswith("An error occurred:") else "completed"
        except Exception as exc:  # noqa: BLE001 - expose worker failures to the UI
            with self.lock:
                run.reply, run.state = str(exc), "failed"
        finally:
            with self.lock:
                if self.cancelled.is_set():
                    run.state, run.reply = "cancelled", "指示を取り消しました。"

    def reset(self):
        """Discard history and agent memory without reconnecting the robot."""
        with self.lock:
            if self.closed or (self.worker and self.worker.is_alive()):
                raise RuntimeError(
                    "実行中は会話をリセットできません。処理の終了後にお試しください。"
                )
            self.runs.clear()
            self.agent = None
            self.worker = None
            self.cancelled.clear()

    def stop(self):
        self.cancelled.set()
        self.robot.motion.block(True)
        if self.robot.motion.enabled:
            return self.robot.motion.stop()
        return {"state": "disabled"}

    def close(self):
        with self.lock:
            self.closed = True
        self.stop()
