from app.services import groq_client


def transcribe_bytes(data: bytes, filename: str = "audio.wav") -> dict:
    """Return {text, language, duration_sec}."""
    if not data:
        raise ValueError("empty audio")

    result = groq_client.transcribe(data, filename=filename)
    return {
        "text": result.get("text", ""),
        "language": result.get("language"),
        "duration_sec": result.get("duration"),
    }
