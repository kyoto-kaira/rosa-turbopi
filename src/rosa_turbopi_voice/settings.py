"""Voice settings, independent of the conversation model and endpoint."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

MAX_AUDIO_BYTES = 4 * 1024 * 1024
TRANSCRIBE_TIMEOUT_S = 45


@dataclass(frozen=True)
class VoiceSettings:
    api_key: str
    model: str = "gpt-transcribe"

    @classmethod
    def load(cls):
        load_dotenv()
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("VOICE_TRANSCRIBE_MODEL", "gpt-transcribe").strip(),
        )
