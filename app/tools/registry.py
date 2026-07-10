from dataclasses import dataclass
from typing import Callable

from app.tools import (
    code_explain,
    compare_texts,
    conversational,
    sentiment,
    summarize,
    youtube,
)


@dataclass(frozen=True)
class Tool:
    name: str
    fn: Callable[..., dict]
    description: str
    params: dict[str, str]  # arg_name -> "str | list[str] | ..."


_TOOLS: dict[str, Tool] = {
    "summarize": Tool(
        name="summarize",
        fn=summarize.run,
        description=summarize.DESCRIPTION,
        params={"context": "str"},
    ),
    "sentiment": Tool(
        name="sentiment",
        fn=sentiment.run,
        description=sentiment.DESCRIPTION,
        params={"context": "str"},
    ),
    "code_explain": Tool(
        name="code_explain",
        fn=code_explain.run,
        description=code_explain.DESCRIPTION,
        params={"context": "str"},
    ),
    "compare_texts": Tool(
        name="compare_texts",
        fn=compare_texts.run,
        description=compare_texts.DESCRIPTION,
        params={"text_a": "str", "text_b": "str"},
    ),
    "youtube_transcript": Tool(
        name="youtube_transcript",
        fn=youtube.run,
        description=youtube.DESCRIPTION,
        params={"source": "str (url or 11-char video id)"},
    ),
    "conversational": Tool(
        name="conversational",
        fn=conversational.run,
        description=conversational.DESCRIPTION,
        params={"context": "str"},
    ),
}


def get(name: str) -> Tool:
    if name not in _TOOLS:
        raise KeyError(f"unknown tool: {name}")
    return _TOOLS[name]


def names() -> list[str]:
    return list(_TOOLS.keys())


def describe_for_planner() -> str:
    """Human-readable dump of tools for the planner prompt."""
    lines = []
    for t in _TOOLS.values():
        params = ", ".join(f"{k}: {v}" for k, v in t.params.items())
        lines.append(f"- {t.name}({params})\n    {t.description}")
    return "\n".join(lines)
