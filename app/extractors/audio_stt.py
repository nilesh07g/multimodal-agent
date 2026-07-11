from app.services import groq_client


def transcribe_bytes(data: bytes, filename: str = "audio.wav") -> dict:
    """Return {text, language, duration_sec}."""
    if not data:
        raise ValueError("empty audio")

    result = groq_client.transcribe(data, filename=filename)
    dur = result.get("duration")
    return {
        "text": result.get("text", ""),
        "language": result.get("language"),
        "duration_sec": round(float(dur), 1) if dur is not None else None,
    }
