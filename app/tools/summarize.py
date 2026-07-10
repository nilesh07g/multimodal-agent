from app.models.schemas import SummarizeResult
from app.services.gemini import generate_validated

DESCRIPTION = (
    "Summarize a text into three formats simultaneously: a one-line summary, "
    "exactly 3 bullet points, and a 5-sentence summary. Use when the user asks "
    "for a summary, TL;DR, or overview of any content (docs, transcripts, etc.)."
)

_SYSTEM = (
    "You produce concise, faithful summaries. Do not add facts not in the source. "
    "Return JSON only, no code fences, no prose outside the JSON."
)


def _prompt(context: str) -> str:
    return f"""Summarize the following content in three formats.

Return JSON with exactly these keys:
- one_liner: a single sentence capturing the core idea
- bullets: an array of exactly 3 short bullet points, each a full sentence
- five_sentence: a 5-sentence paragraph summary

Content:
\"\"\"
{context}
\"\"\""""


def run(context: str) -> dict:
    if not context or not context.strip():
        raise ValueError("summarize: empty context")
    result = generate_validated(_prompt(context), SummarizeResult, system=_SYSTEM)
    return result.model_dump()
