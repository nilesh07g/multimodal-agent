import time
from typing import Any

from app.models.schemas import Plan, PlanTraceStep, ToolStep
from app.tools import registry


PRIMARY_FIELD = {
    "summarize": "five_sentence",
    "sentiment": "justification",
    "code_explain": "explanation",
    "compare_texts": "summary",
    "youtube_transcript": "transcript",
    "conversational": "reply",
}


def _preview(s: Any, cap: int = 200) -> str:
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return ""
    s = s.strip()
    if len(s) <= cap:
        return s
    return s[:cap].rstrip() + "…"


def _resolve(value: Any, artifacts: dict[str, Any], prev_primary: str) -> Any:
    """Replace $artifact / $prev references with actual values. Non-string args pass through."""
    if not isinstance(value, str):
        return value
    v = value.strip()
    if v == "$prev":
        return prev_primary
    if v.startswith("$") and v in artifacts:
        return artifacts[v]
    return value


def _resolve_args(args: dict[str, Any], artifacts: dict[str, Any], prev_primary: str) -> dict[str, Any]:
    return {k: _resolve(v, artifacts, prev_primary) for k, v in args.items()}


def _primary_text(tool_name: str, result: dict[str, Any]) -> str:
    field = PRIMARY_FIELD.get(tool_name)
    if field and isinstance(result.get(field), str):
        return result[field]
    # fallback: any string field
    for v in result.values():
        if isinstance(v, str) and v.strip():
            return v
    return ""


def execute(plan: Plan, artifacts: dict[str, Any]) -> tuple[list[PlanTraceStep], list[dict[str, Any]]]:
    """Run each step. Returns (trace, raw_results). raw_results preserves each tool's full output."""
    trace: list[PlanTraceStep] = []
    raw_results: list[dict[str, Any]] = []
    prev_primary = ""

    for i, step in enumerate(plan.steps, start=1):
        resolved_args = _resolve_args(step.args, artifacts, prev_primary)
        started = time.perf_counter()
        try:
            tool = registry.get(step.tool)
            result = tool.fn(**resolved_args)
            duration_ms = int((time.perf_counter() - started) * 1000)
            primary = _primary_text(step.tool, result)
            trace.append(PlanTraceStep(
                step_number=i,
                tool=step.tool,
                args={k: _preview(v, 120) for k, v in resolved_args.items()},
                reason=step.reason,
                output_preview=_preview(primary),
                duration_ms=duration_ms,
                status="ok",
            ))
            raw_results.append({"tool": step.tool, "result": result})
            prev_primary = primary
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            trace.append(PlanTraceStep(
                step_number=i,
                tool=step.tool,
                args={k: _preview(v, 120) for k, v in resolved_args.items()},
                reason=step.reason,
                output_preview="",
                duration_ms=duration_ms,
                status="error",
                error=str(e),
            ))
            raw_results.append({"tool": step.tool, "error": str(e)})
            # don't propagate previous primary if a step errored
            prev_primary = ""

    return trace, raw_results
