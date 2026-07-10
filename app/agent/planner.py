from app.models.schemas import Plan, ToolStep
from app.services.gemini import generate_validated
from app.tools import registry

_SYSTEM = (
    "You plan the shortest useful sequence of tool calls to satisfy the user's "
    "request given the extracted content. Prefer 1 step. Never invent tools not "
    "in the registry. Never invent artifact names not in the artifact list. "
    "Return JSON only."
)


def _prompt(query: str, extraction_summary: str, artifact_names: list[str]) -> str:
    tools_desc = registry.describe_for_planner()
    return f"""Available tools:
{tools_desc}

Available artifact references (use these as string arg values instead of copying big text):
{", ".join(artifact_names)}
Additionally, you may write "$prev" inside any step after the first to refer to the previous step's primary text output.

Situation:
{extraction_summary}

Compose a plan as JSON with:
- steps: array of {{tool, args, reason}}
- overall_reason: one sentence explaining the plan

Rules:
- Pick the minimum number of steps. Prefer 1. Chain only if strictly needed.
- If a YouTube URL is present AND the query implies watching/summarising it, plan: youtube_transcript(source="$youtube_url") -> summarize(context="$prev").
- If PDF + audio are both present AND the query implies comparing them, plan: compare_texts(text_a="$pdf_text", text_b="$audio_text").
- If an image with code is present AND the query implies explaining code, plan: code_explain(context="$image_text").
- If the query implies summarize but the content is one PDF/audio, plan: summarize(context="$extracted_all").
- If the query implies sentiment, plan: sentiment(context="$extracted_all").
- If none of the above clearly fits, plan: conversational(context="$extracted_all").
- args must use the exact param names declared by each tool.

Example JSON:
{{"steps":[{{"tool":"summarize","args":{{"context":"$extracted_all"}},"reason":"user asked for a tldr"}}],"overall_reason":"single summarize call covers the request"}}"""


def _fallback_plan() -> Plan:
    return Plan(
        steps=[ToolStep(tool="conversational", args={"context": "$extracted_all"},
                        reason="planner failed validation twice, using conversational fallback")],
        overall_reason="fallback: safe conversational response",
    )


def plan(query: str, extraction_summary: str, artifact_names: list[str]) -> Plan:
    try:
        p = generate_validated(
            _prompt(query, extraction_summary, artifact_names),
            Plan,
            system=_SYSTEM,
            temperature=0.1,
        )
    except Exception:
        return _fallback_plan()

    valid_tools = set(registry.names())
    p.steps = [s for s in p.steps if s.tool in valid_tools]
    if not p.steps:
        return _fallback_plan()
    return p
