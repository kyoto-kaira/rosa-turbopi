"""Compose voice input around the original application without changing it."""

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from rosa_turbopi.web.app import create_app as create_base_app
from rosa_turbopi_voice.providers.openai import OpenAITranscriber
from rosa_turbopi_voice.routes import create_router
from rosa_turbopi_voice.settings import VoiceSettings

ASSETS = (
    '<link rel="stylesheet" href="/voice/static/voice.css">'
    '<script src="/voice/static/voice.js" defer></script>'
)


def create_app(settings=None, agent_factory=None, transcriber=None):
    app = create_base_app(settings, agent_factory)
    app.include_router(create_router(transcriber or OpenAITranscriber(VoiceSettings.load())))
    app.mount(
        "/voice/static",
        StaticFiles(directory=Path(__file__).parent / "static"),
        name="voice-static",
    )
    # Decorate only the initial page. The original SSE, forms and lifespan stay intact.
    original = next(route for route in app.routes if getattr(route, "path", None) == "/")
    app.routes.remove(original)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        response = original.endpoint(request)
        return HTMLResponse(response.body.decode().replace("</head>", ASSETS + "</head>", 1))

    return app


def main():
    import uvicorn

    uvicorn.run("rosa_turbopi_voice.app:create_app", factory=True, host="127.0.0.1", port=8000)
