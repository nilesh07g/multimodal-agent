from app.models.schemas import CodeExplainResult
from app.services.gemini import generate_validated

DESCRIPTION = (
    "Explain what a code snippet does, flag likely bugs, and estimate time "
    "complexity. Use when the input contains source code and the user wants "
    "an explanation, bug review, or complexity analysis."
)

_SYSTEM = (
    "You review code carefully. Be honest about bugs — do not invent them, do "
    "not miss obvious ones. Return JSON only."
)


def _prompt(context: str) -> str:
    return f"""Analyse the following code.

Return JSON with exactly these keys:
- language: the programming language, e.g. "python", "javascript", "go" (best guess). null if unclear.
- explanation: 2-4 sentences describing what the code does end-to-end.
- bugs: an array of strings, one per suspected bug or foot-gun. Empty array if the code looks correct.
- time_complexity: worst-case big-O of the main routine, e.g. "O(n)", "O(n log n)", "O(1)". If mixed or unclear, describe briefly.

Code:
\"\"\"
{context}
\"\"\""""


def run(context: str) -> dict:
    if not context or not context.strip():
        raise ValueError("code_explain: empty context")
    result = generate_validated(_prompt(context), CodeExplainResult, system=_SYSTEM)
    return result.model_dump()
