from app.models.schemas import SentimentResult
from app.services.gemini import generate_validated

DESCRIPTION = (
    "Classify sentiment of a text as positive/negative/neutral/mixed with a "
    "confidence score and a one-line justification. Use when the user asks how "
    "someone feels, the tone of the content, or to gauge opinion."
)

_SYSTEM = (
    "You classify sentiment precisely. Return JSON only."
)


def _prompt(context: str) -> str:
    return f"""Classify the sentiment of the content.

Return JSON with exactly these keys:
- label: one of "positive", "negative", "neutral", "mixed"
- confidence: a float between 0.0 and 1.0
- justification: one short sentence explaining the choice

Content:
\"\"\"
{context}
\"\"\""""


def run(context: str) -> dict:
    if not context or not context.strip():
        raise ValueError("sentiment: empty context")
    result = generate_validated(_prompt(context), SentimentResult, system=_SYSTEM)
    return result.model_dump()
