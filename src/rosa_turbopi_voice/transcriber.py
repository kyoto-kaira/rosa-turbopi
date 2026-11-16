"""Provider boundary; transcription never submits robot commands."""

from typing import Protocol


class TranscriptionError(Exception):
    """A safe, user-facing transcription failure."""


class Transcriber(Protocol):
    async def transcribe(self, audio: bytes, media_type: str, extension: str) -> str: ...
