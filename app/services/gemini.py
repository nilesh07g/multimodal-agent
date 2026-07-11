import json
import re
import time
from typing import Optional, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import settings

T = TypeVar("T", bound=BaseModel)


def _parse_retry_delay(err: Exception) -> float:
    """Pull Google's suggested retry delay out of a 429 error, if present.
    Falls back to 0 if not found."""
    msg = str(err)
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'", msg)
    if m:
        return float(m.group(1))
    return 0.0


def _is_rate_limit(err: Exception) -> bool:
    s = str(err)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()

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
            if attempt >= max_retries:
                break
            # rate limits: fail fast so the route can return a friendly retry msg
            # (waiting google's suggested 30-60s delay blows past render's proxy timeout)
            if _is_rate_limit(e):
                break
            # transient network errors: short backoff and retry
            time.sleep([2.0, 5.0][min(attempt, 1)])
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
            if attempt >= max_retries:
                break
            # rate limits: fail fast so the route can return a friendly retry msg
            # (waiting google's suggested 30-60s delay blows past render's proxy timeout)
            if _is_rate_limit(e):
                break
            # transient network errors: short backoff and retry
            time.sleep([2.0, 5.0][min(attempt, 1)])
    raise last_err


def generate_validated(prompt: str, model_cls: Type[T], *, system: str = "", temperature: float = 0.1) -> T:
    """Call Gemini for JSON, validate against `model_cls`. On JSON/validation error, retry once
    with the error appended so the model can self-correct."""
    raw = generate_json(prompt, system=system, temperature=temperature)
    try:
        return model_cls(**json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as first_err:
        retry_prompt = (
            f"{prompt}\n\n---\n"
            f"Your previous output failed schema validation with error: {first_err}\n"
            f"Return valid JSON matching the required schema. No prose, no code fences."
        )
        raw = generate_json(retry_prompt, system=system, temperature=temperature)
        return model_cls(**json.loads(raw))
