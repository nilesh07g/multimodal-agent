import time
from typing import Optional

from google import genai
from google.genai import types

from app.config import settings

_client: Optional[genai.Client] = None


def client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def generate_text(prompt: str, *, system: str = "", temperature: float = 0.2, max_retries: int = 2) -> str:
    """Plain text generation. Retries on transient errors."""
    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        temperature=temperature,
    )
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = client().models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=cfg,
            )
            return (resp.text or "").strip()
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(0.6 * (attempt + 1))
    raise last_err


def generate_json(prompt: str, *, system: str = "", temperature: float = 0.1, max_retries: int = 2) -> str:
    """Generation constrained to a JSON response. Caller parses + validates via Pydantic."""
    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        temperature=temperature,
        response_mime_type="application/json",
    )
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = client().models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=cfg,
            )
            return (resp.text or "").strip()
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(0.6 * (attempt + 1))
    raise last_err
