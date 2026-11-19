"""Local robot console. Run one worker to share robot ownership."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from rosa_turbopi.execution.service import ExecutionService
from rosa_turbopi.robot.camera.source import CaptureError
from rosa_turbopi.robot.client import TurboPiClient
from rosa_turbopi.settings import Settings
from rosa_turbopi.tools.catalog import describe_tools
from rosa_turbopi.transport.mock import MockTransport
from rosa_turbopi.transport.rosbridge import RosbridgeClient
from rosa_turbopi.web.summaries import tool_summary

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
        app.state.camera_http = httpx.AsyncClient(
            timeout=httpx.Timeout(config.camera_timeout_s), trust_env=False
        )
        app.state.notice = ""
        app.state.notice_error = False
        try:
            await asyncio.to_thread(transport.connect, timeout=config.timeout_s)
            yield
        finally:
            try:
                await asyncio.to_thread(service.close)
            finally:
                transport.close()
                await app.state.camera_http.aclose()

    app = FastAPI(lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")
    templates.env.globals["tool_summary"] = tool_summary

    def render(request, selected=None, template="partials/workspace.html"):
        runs = request.app.state.service.snapshot()
        chosen = next((run for run in runs if run.id == selected), runs[-1] if runs else None)
        index = next((i for i, run in enumerate(runs) if run is chosen), -1)
        return templates.TemplateResponse(
            request=request,
            name=template,
            context={
                "runs": runs,
                "selected": chosen,
                "previous_run": runs[index - 1] if index > 0 else None,
                "next_run": runs[index + 1] if 0 <= index < len(runs) - 1 else None,
                "latest_run": runs[-1] if runs else None,
                "busy": any(r.state == "running" for r in runs),
                "status": request.app.state.robot.status(),
                "notice": request.app.state.notice,
                "notice_error": request.app.state.notice_error,
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
            request.app.state.notice_error = False
        except (RuntimeError, ValueError) as exc:
            request.app.state.notice = str(exc)
            request.app.state.notice_error = True
        return render(request)

    @app.post("/conversation/reset", response_class=HTMLResponse)
    def reset(request: Request):
        try:
            request.app.state.service.reset()
        except RuntimeError as exc:
            request.app.state.notice = str(exc)
            request.app.state.notice_error = True
            return render(request)
        request.app.state.notice = ""
        request.app.state.notice_error = False
        response = render(request)
        response.headers["HX-Trigger"] = "conversationReset"
        return response

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def history(request: Request, run_id: str):
        return render(request, selected=run_id)

    @app.post("/stop", response_class=HTMLResponse)
    def stop(request: Request):
        try:
            result = request.app.state.service.stop()
            request.app.state.notice_error = False
            request.app.state.notice = (
                "停止指令は無効です。"
                if result["state"] == "disabled"
                else "取消を要求し、停止指令を送信しました。"
            )
        except (ValueError, PermissionError, ConnectionError, RuntimeError, TimeoutError) as exc:
            request.app.state.notice = f"停止処理に失敗しました: {exc}"
            request.app.state.notice_error = True
        return render(request)

    @app.get("/tools", response_class=HTMLResponse)
    def tools(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="partials/tools.html",
            context={"groups": describe_tools(request.app.state.robot)},
        )

    @app.get("/camera")
    def camera(request: Request):
        camera = request.app.state.robot.camera
        if camera is None:
            return Response(status_code=204)
        try:
            frame = camera.capture()
        except CaptureError as exc:
            # The robot's camera did not answer; report it instead of a server error.
            return Response(
                str(exc),
                status_code=503,
                media_type="text/plain",
                headers={"Cache-Control": "no-store"},
            )
        return Response(
            frame.data,
            media_type=frame.media_type,
            headers={
                "Cache-Control": "no-store",
                "X-Frame-ID": frame.id,
                "X-Captured-At": frame.captured_at.isoformat(),
            },
        )

    @app.get("/detections/{frame_id}", response_class=HTMLResponse)
    def detection_view(request: Request, frame_id: str, thumbnail: bool = False):
        record = request.app.state.robot.detection_frames.get(frame_id)
        return templates.TemplateResponse(
            request=request,
            name="detection.html",
            context={"record": record, "thumbnail": thumbnail},
            status_code=200 if record else 404,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/detections/{frame_id}/image")
    def detection_image(request: Request, frame_id: str):
        record = request.app.state.robot.detection_frames.get(frame_id)
        if record is None:
            return Response(status_code=404)
        return Response(
            record.frame.data,
            media_type=record.frame.media_type,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/camera/stream")
    async def camera_stream(request: Request):
        config = request.app.state.robot.settings
        if config.backend != "rosbridge":
            return Response(status_code=204)
        query = urlencode({"topic": config.camera_topic, "type": "mjpeg"}, safe="/")
        url = f"http://{config.host}:{config.camera_port}/stream?{query}"
        client = request.app.state.camera_http
        upstream = None
        try:
            upstream = await client.send(client.build_request("GET", url), stream=True)
            upstream.raise_for_status()
            content_type = upstream.headers.get("content-type", "")
            if (
                content_type.split(";", 1)[0].strip().lower() != "multipart/x-mixed-replace"
                or "boundary=" not in content_type.lower()
            ):
                raise ValueError("Camera endpoint did not return an MJPEG stream")
        except (httpx.HTTPError, ValueError):
            if upstream is not None:
                await upstream.aclose()
            return Response("Camera stream unavailable", status_code=503)

        async def frames():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            except httpx.HTTPError:
                # Ending the response lets the browser reconnect after an upstream failure.
                return
            finally:
                await upstream.aclose()

        return StreamingResponse(
            frames(),
            headers={
                "Content-Type": content_type,
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
            background=BackgroundTask(upstream.aclose),
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
