import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from rosa_turbopi.settings import Settings
from rosa_turbopi.web.app import create_app as create_base_app
from rosa_turbopi_voice.app import create_app
from rosa_turbopi_voice.providers.openai import OpenAITranscriber
from rosa_turbopi_voice.routes import create_router
from rosa_turbopi_voice.settings import MAX_AUDIO_BYTES, VoiceSettings
from rosa_turbopi_voice.transcriber import TranscriptionError


def provider_with_transport(settings, transport):
    def client_factory(**kwargs):
        return AsyncOpenAI(http_client=httpx.AsyncClient(transport=transport), **kwargs)

    return OpenAITranscriber(settings, client_factory=client_factory)


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    async def transcribe(self, audio, media_type, extension):
        self.calls.append((audio, media_type, extension))
        return "1秒前進して"


def settings():
    return Settings("localhost", 9090, False, "/battery", "std_msgs/UInt16", 1, "", backend="mock")


def test_extension_preserves_base_app_and_never_submits_transcript():
    fake = FakeTranscriber()
    with TestClient(create_app(settings(), transcriber=fake)) as client:
        html = client.get("/").text
        assert "/voice/static/voice.js" in html
        assert 'id="query"' in html
        assert client.get("/voice/static/voice.js").status_code == 200
        assert client.get("/voice/static/voice.css").status_code == 200
        response = client.post(
            "/voice/transcribe",
            content=b"audio",
            headers={"Content-Type": "audio/webm;codecs=opus"},
        )
        assert response.json() == {"text": "1秒前進して"}
        assert response.headers["cache-control"] == "no-store"
        assert fake.calls == [(b"audio", "audio/webm", "webm")]
        assert client.app.state.service.snapshot() == []
        assert client.get("/camera").status_code == 200
        assert client.post("/stop").status_code == 200
    with TestClient(create_base_app(settings())) as client:
        assert "/voice/static/" not in client.get("/").text
        assert client.post("/voice/transcribe").status_code == 404


def test_input_limits_and_safe_provider_error():
    fake = FakeTranscriber()
    app = FastAPI()
    app.include_router(create_router(fake))
    with TestClient(app) as client:
        assert client.post("/voice/transcribe", content=b"x").status_code == 415
        for content, expected in [(b"", 400), (b"x" * (MAX_AUDIO_BYTES + 1), 413)]:
            assert (
                client.post(
                    "/voice/transcribe", content=content, headers={"Content-Type": "audio/webm"}
                ).status_code
                == expected
            )
        assert fake.calls == []

    class Failed:
        async def transcribe(self, *args):
            raise TranscriptionError("もう一度録音してください。")

    app = FastAPI()
    app.include_router(create_router(Failed()))
    with TestClient(app) as client:
        result = client.post(
            "/voice/transcribe", content=b"x", headers={"Content-Type": "audio/mp4"}
        )
        assert result.status_code == 502
        assert result.json()["detail"] == "もう一度録音してください。"


def test_streamed_upload_is_bounded_and_concurrent_requests_rejected():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        class Waiting:
            async def transcribe(self, *args):
                entered.set()
                await release.wait()
                return "結果"

        app = FastAPI()
        app.include_router(create_router(Waiting()))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as c:

            async def chunks():
                yield b"x" * MAX_AUDIO_BYTES
                yield b"y"

            oversized = await c.post(
                "/voice/transcribe", content=chunks(), headers={"Content-Type": "audio/webm"}
            )
            assert oversized.status_code == 413
            first = asyncio.create_task(
                c.post("/voice/transcribe", content=b"x", headers={"Content-Type": "audio/webm"})
            )
            await asyncio.wait_for(entered.wait(), 2)
            try:
                second = await c.post(
                    "/voice/transcribe", content=b"x", headers={"Content-Type": "audio/webm"}
                )
                assert second.status_code == 429
            finally:
                release.set()
                assert (await first).status_code == 200

    asyncio.run(run())


def test_provider_uses_shared_key_and_fixed_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://other-provider.invalid")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("VOICE_TRANSCRIBE_MODEL", "test-model")

    def handle(request):
        assert str(request.url) == "https://api.openai.com/v1/audio/transcriptions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = request.read()
        assert b"test-model" in body
        assert b"recording.mp4" in body
        assert b"fake-audio" in body
        return httpx.Response(200, json={"text": "  左に1秒移動  "})

    provider = provider_with_transport(VoiceSettings.load(), httpx.MockTransport(handle))
    assert asyncio.run(provider.transcribe(b"fake-audio", "audio/mp4", "mp4")) == "左に1秒移動"


@pytest.mark.parametrize(
    "result",
    [
        httpx.Response(401, text="secret upstream response"),
        httpx.Response(429),
        httpx.Response(500),
        httpx.Response(200, text="invalid json"),
        httpx.Response(200, json={"text": ""}),
        httpx.Response(200, json={"text": "x" * 4001}),
        httpx.Response(200, json=[]),
    ],
)
def test_provider_errors_do_not_expose_upstream_details(result):
    provider = provider_with_transport(
        VoiceSettings("private-key"), httpx.MockTransport(lambda request: result)
    )
    with pytest.raises(TranscriptionError) as error:
        asyncio.run(provider.transcribe(b"audio", "audio/webm", "webm"))
    assert "secret" not in str(error.value)
    assert "private-key" not in str(error.value)


def test_provider_timeout_and_missing_key():
    def timeout(request):
        raise httpx.ReadTimeout("private details", request=request)

    provider = provider_with_transport(VoiceSettings("test"), httpx.MockTransport(timeout))
    with pytest.raises(TranscriptionError, match="タイムアウト"):
        asyncio.run(provider.transcribe(b"audio", "audio/webm", "webm"))
    provider = provider_with_transport(VoiceSettings(""), httpx.MockTransport(timeout))
    with pytest.raises(TranscriptionError, match="OPENAI_API_KEY"):
        asyncio.run(provider.transcribe(b"audio", "audio/webm", "webm"))
