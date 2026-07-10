from typing import Any

from app.agent import clarifier, context, executor, planner
from app.models.schemas import PlanTraceStep


def _compose_answer(raw_results: list[dict[str, Any]]) -> str:
    """Format the last successful step's output as the user-facing answer."""
    successes = [r for r in raw_results if "result" in r]
    if not successes:
        return "sorry, i couldn't complete any step of the plan."

    last = successes[-1]
    tool = last["tool"]
    r = last["result"]

    if tool == "summarize":
        bullets = "\n".join(f"• {b}" for b in r.get("bullets", []))
        return (
            f"**one-liner**\n{r.get('one_liner','')}\n\n"
            f"**3 bullets**\n{bullets}\n\n"
            f"**5-sentence summary**\n{r.get('five_sentence','')}"
        )
    if tool == "sentiment":
        return (
            f"**sentiment:** {r.get('label','')}  "
            f"(confidence {r.get('confidence',0):.2f})\n\n"
            f"{r.get('justification','')}"
        )
    if tool == "code_explain":
        bugs = r.get("bugs") or []
        bugs_txt = "\n".join(f"• {b}" for b in bugs) if bugs else "no obvious bugs detected."
        lang = r.get("language") or "unknown"
        return (
            f"**language:** {lang}\n\n"
            f"**what it does**\n{r.get('explanation','')}\n\n"
            f"**bugs / concerns**\n{bugs_txt}\n\n"
            f"**time complexity:** {r.get('time_complexity','')}"
        )
    if tool == "compare_texts":
        sims = "\n".join(f"• {x}" for x in r.get("similarities", [])) or "—"
        diffs = "\n".join(f"• {x}" for x in r.get("differences", [])) or "—"
        yn = "yes" if r.get("same_topic") else "no"
        return (
            f"**same topic:** {yn}\n\n"
            f"**summary**\n{r.get('summary','')}\n\n"
            f"**similarities**\n{sims}\n\n"
            f"**differences**\n{diffs}"
        )
    if tool == "youtube_transcript":
        if r.get("fallback_used"):
            return f"couldn't fetch transcript from {r.get('source_url','')}: {r.get('note','')}"
        return f"transcript ({r.get('source_url','')}):\n\n{r.get('transcript','')}"
    if tool == "conversational":
        return r.get("reply", "")
    # unknown tool shape — dump what we have
    return str(r)


def run(query: str, extracted: dict[str, Any]) -> dict[str, Any]:
    artifacts = context.build(query, extracted)
    summary = context.summarize_for_planner(query, extracted, artifacts)

    # 1. clarifier gate
    try:
        c = clarifier.check(query, summary)
    except Exception:
        # clarifier failure -> proceed rather than block
        c = None

    if c and c.needed and c.question:
        return {
            "answer": "",
            "follow_up": c.question,
            "plan": None,
            "plan_trace": [],
        }

    # 2. plan
    artifact_names = [k for k in artifacts.keys() if k.startswith("$")]
    plan = planner.plan(query, summary, artifact_names)

    # 3. execute
    trace, raw_results = executor.execute(plan, artifacts)

    # 4. compose
    answer = _compose_answer(raw_results)

    return {
        "answer": answer,
        "follow_up": None,
        "plan": {
            "overall_reason": plan.overall_reason,
            "steps": [{"tool": s.tool, "args": s.args, "reason": s.reason} for s in plan.steps],
        },
        "plan_trace": [t.model_dump() for t in trace],
    }
