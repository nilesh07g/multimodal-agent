import io
import time
from typing import Optional

from groq import Groq

from app.config import settings

_client: Optional[Groq] = None


def client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def transcribe(audio_bytes: bytes, filename: str = "audio.wav", *, max_retries: int = 2) -> dict:
    """Groq Whisper. Returns {text, language, duration}."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            buf = io.BytesIO(audio_bytes)
            buf.name = filename
            resp = client().audio.transcriptions.create(
                file=(filename, buf.getvalue()),
                model=settings.whisper_model,
                response_format="verbose_json",
            )
            data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
            return {
                "text": (data.get("text") or "").strip(),
                "language": data.get("language"),
                "duration": data.get("duration"),
            }
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(0.8 * (attempt + 1))
    raise last_err
