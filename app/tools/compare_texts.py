from app.models.schemas import CompareResult
from app.services.gemini import generate_validated

DESCRIPTION = (
    "Compare two texts to decide whether they discuss the same topic, and list "
    "similarities and differences. Use when the user has multiple inputs and "
    "asks whether they overlap, agree, differ, or cover the same subject."
)

_SYSTEM = (
    "You compare texts objectively. Return JSON only."
)


def _prompt(a: str, b: str) -> str:
    return f"""Compare the two texts below.

Return JSON with exactly these keys:
- same_topic: true or false — do they discuss the same overall subject?
- similarities: array of short strings, key overlaps in content or claim
- differences: array of short strings, key divergences
- summary: one paragraph (2-3 sentences) overall comparative verdict

Text A:
\"\"\"
{a}
\"\"\"

Text B:
\"\"\"
{b}
\"\"\""""


def run(text_a: str, text_b: str) -> dict:
    if not text_a or not text_a.strip() or not text_b or not text_b.strip():
        raise ValueError("compare_texts: both inputs required")
    result = generate_validated(_prompt(text_a, text_b), CompareResult, system=_SYSTEM)
    return result.model_dump()
