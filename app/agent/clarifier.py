from app.models.schemas import Clarification
from app.services.gemini import generate_validated

_SYSTEM = (
    "You decide whether the user's request is clear enough to act on. Only ask "
    "a follow-up if the intent is genuinely ambiguous or multiple very different "
    "tasks are equally plausible. Prefer acting over asking."
)


def _prompt(query: str, extraction_summary: str) -> str:
    return f"""User query:
\"\"\"
{query or "(empty)"}
\"\"\"

What was extracted from the user's uploads:
{extraction_summary or "(nothing uploaded)"}

Decide whether the request is clear enough to proceed. Return JSON with:
- needed: true or false
- question: if needed=true, a single concise follow-up question to ask. If needed=false, null.

Guidance:
- If the query names a specific task (summarize, sentiment, transcribe, explain code, fetch youtube, compare, answer), needed=false.
- If files are attached but the query is empty, and there's exactly one obvious next step (e.g., only a PDF -> summarize is a reasonable default), needed=false.
- If files are attached and the query is empty AND multiple very different tasks apply (e.g., audio + text + image with no direction), needed=true.
- If the query is a single vague word like "help" or "?", needed=true.
- Prefer acting. Only ask if truly stuck."""


def check(query: str, extraction_summary: str) -> Clarification:
    return generate_validated(
        _prompt(query, extraction_summary),
        Clarification,
        system=_SYSTEM,
        temperature=0.0,
    )
