"""Receive raw audio without multipart spooling or persistent recordings."""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from rosa_turbopi_voice.settings import MAX_AUDIO_BYTES
from rosa_turbopi_voice.transcriber import Transcriber, TranscriptionError

MEDIA_TYPES = {"audio/webm": "webm", "audio/mp4": "mp4", "audio/wav": "wav"}


def create_router(transcriber: Transcriber):
    router = APIRouter(prefix="/voice")
    lock = asyncio.Lock()

    @router.post("/transcribe")
    async def transcribe(request: Request):
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media_type not in MEDIA_TYPES:
            raise HTTPException(415, "対応していない録音形式です。")
        if lock.locked():
            raise HTTPException(429, "文字起こし中です。完了してからお試しください。")
        async with lock:
            audio = bytearray()
            async for chunk in request.stream():
                if len(audio) + len(chunk) > MAX_AUDIO_BYTES:
                    raise HTTPException(413, "録音データが大きすぎます。短く録音してください。")
                audio.extend(chunk)
            if not audio:
                raise HTTPException(400, "録音データが空です。")
            try:
                text = await transcriber.transcribe(
                    bytes(audio), media_type, MEDIA_TYPES[media_type]
                )
            except TranscriptionError as exc:
                raise HTTPException(502, str(exc)) from exc
        return JSONResponse({"text": text}, headers={"Cache-Control": "no-store"})

    return router
