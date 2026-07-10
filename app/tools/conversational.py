from app.models.schemas import ConversationalResult
from app.services.gemini import generate_text

DESCRIPTION = (
    "Answer a general question conversationally. Fallback tool when no other "
    "task applies — greetings, casual questions, or turns where the extracted "
    "content doesn't fit any specific analysis task."
)

_SYSTEM = (
    "You are a helpful assistant embedded in a multimodal agent. Be concise, "
    "friendly, and honest. If the user hasn't given enough context, say so."
)


def run(context: str) -> dict:
    text = (context or "").strip()
    if not text:
        text = "The user hasn't provided any input yet."
    reply = generate_text(text, system=_SYSTEM, temperature=0.4)
    return ConversationalResult(reply=reply).model_dump()
