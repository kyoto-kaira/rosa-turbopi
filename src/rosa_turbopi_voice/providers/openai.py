"""Upload bounded audio directly to OpenAI, ignoring OPENAI_BASE_URL."""

from openai import APIError, APITimeoutError, AsyncOpenAI

from rosa_turbopi_voice.settings import TRANSCRIBE_TIMEOUT_S, VoiceSettings
from rosa_turbopi_voice.transcriber import TranscriptionError


class OpenAITranscriber:
    def __init__(self, settings: VoiceSettings, client_factory=AsyncOpenAI):
        self.settings = settings
        self.client_factory = client_factory

    async def transcribe(self, audio: bytes, media_type: str, extension: str) -> str:
        if not self.settings.api_key or not self.settings.model:
            raise TranscriptionError(
                "OPENAI_API_KEY と VOICE_TRANSCRIBE_MODEL の設定を確認してください。"
            )
        try:
            async with self.client_factory(
                api_key=self.settings.api_key,
                base_url="https://api.openai.com/v1",
                timeout=TRANSCRIBE_TIMEOUT_S,
                max_retries=0,
            ) as client:
                result = await client.audio.transcriptions.create(
                    model=self.settings.model,
                    file=(f"recording.{extension}", audio, media_type),
                )
                text = result.text
        except APITimeoutError as exc:
            raise TranscriptionError(
                "文字起こしがタイムアウトしました。再度お試しください。"
            ) from exc
        except (APIError, ValueError, AttributeError) as exc:
            raise TranscriptionError(
                "文字起こしAPIへの接続に失敗しました。設定や利用状況を確認してください。"
            ) from exc
        if not isinstance(text, str) or not text.strip():
            raise TranscriptionError("音声を認識できませんでした。もう一度録音してください。")
        if len(text.strip()) > 4000:
            raise TranscriptionError("認識結果が長すぎます。短く区切って録音してください。")
        return text.strip()
