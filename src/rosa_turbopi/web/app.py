"""Local robot console. Run one worker to share robot ownership."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from rosa_turbopi.execution.service import ExecutionService
from rosa_turbopi.robot.client import TurboPiClient
from rosa_turbopi.settings import Settings
from rosa_turbopi.transport.mock import MockTransport
from rosa_turbopi.transport.rosbridge import RosbridgeClient

ROOT = Path(__file__).parent


def create_app(settings=None, agent_factory=None):
    @asynccontextmanager
    async def lifespan(app):
        config = settings or Settings.load()
        transport = (
            MockTransport(echo=False)
            if config.backend == "mock"
            else RosbridgeClient(
                config.host, config.port, config.secure, enable_motion=config.enable_motion
            )
        )
        robot = TurboPiClient(transport, config)
        service = ExecutionService(robot, agent_factory)
        app.state.service = service
        app.state.robot = robot
        app.state.notice = ""
        try:
            await asyncio.to_thread(transport.connect, timeout=config.timeout_s)
            yield
        finally:
            try:
                await asyncio.to_thread(service.close)
            finally:
                transport.close()

    app = FastAPI(lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")

    def render(request, selected=None, template="partials/workspace.html"):
        runs = request.app.state.service.snapshot()
        chosen = next((run for run in runs if run.id == selected), runs[-1] if runs else None)
        return templates.TemplateResponse(
            request=request,
            name=template,
            context={
                "runs": runs,
                "selected": chosen,
                "busy": any(r.state == "running" for r in runs),
                "status": request.app.state.robot.status(),
                "notice": request.app.state.notice,
                "labels": {
                    "running": "実行中",
                    "completed": "完了",
                    "failed": "失敗",
                    "rejected": "拒否",
                    "cancelled": "取消",
                },
            },
        )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return render(request, template="index.html")

    @app.post("/chat", response_class=HTMLResponse)
    def chat(request: Request, query: str = Form(...)):
        query = query.strip()
        try:
            if not query or len(query) > 4000:
                raise ValueError("指示は1〜4000文字で入力してください。")
            request.app.state.service.submit(query)
            request.app.state.notice = ""
        except (RuntimeError, ValueError) as exc:
            request.app.state.notice = str(exc)
        return render(request)

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def history(request: Request, run_id: str):
        return render(request, selected=run_id)

    @app.post("/stop", response_class=HTMLResponse)
    def stop(request: Request):
        try:
            result = request.app.state.service.stop()
            request.app.state.notice = (
                "停止指令は無効です。"
                if result["state"] == "disabled"
                else "取消を要求し、停止指令を送信しました。"
            )
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            request.app.state.notice = f"停止処理に失敗しました: {exc}"
        return render(request)

    @app.get("/camera")
    def camera(request: Request):
        camera = request.app.state.robot.camera
        if camera is None:
            return Response(status_code=204)
        frame = camera.capture()
        return Response(
            frame.data,
            media_type=frame.media_type,
            headers={
                "Cache-Control": "no-store",
                "X-Frame-ID": frame.id,
                "X-Captured-At": frame.captured_at.isoformat(),
            },
        )

    @app.get("/events")
    async def events(request: Request):
        async def stream():
            previous = None
            while not await request.is_disconnected():
                # Full snapshots make reconnects recover without replaying tool actions.
                current = render(request).body.decode()
                if current != previous:
                    yield (
                        "event: workspace\n"
                        + "".join(f"data: {line}\n" for line in current.splitlines())
                        + "\n"
                    )
                    previous = current
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def main():
    import uvicorn

    uvicorn.run("rosa_turbopi.web.app:create_app", factory=True, host="127.0.0.1", port=8000)
