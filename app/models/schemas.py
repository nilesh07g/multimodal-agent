from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SummarizeResult(BaseModel):
    one_liner: str
    bullets: list[str]
    five_sentence: str

    @field_validator("bullets")
    @classmethod
    def _clean_bullets(cls, v: list[str]) -> list[str]:
        cleaned = [b.strip() for b in v if b and b.strip()]
        if not cleaned:
            raise ValueError("bullets must not be empty")
        # cap at 5 in case the model over-produces; planner spec is 3
        return cleaned[:5]


class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral", "mixed"]
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str


class CodeExplainResult(BaseModel):
    language: Optional[str] = None
    explanation: str
    bugs: list[str] = []
    time_complexity: str


class CompareResult(BaseModel):
    same_topic: bool
    similarities: list[str] = []
    differences: list[str] = []
    summary: str


class YoutubeResult(BaseModel):
    transcript: str
    source_url: str
    video_id: str
    fallback_used: bool = False
    note: Optional[str] = None


class ConversationalResult(BaseModel):
    reply: str


# ---------- agent schemas ----------

class Clarification(BaseModel):
    needed: bool
    question: Optional[str] = None


class ToolStep(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class Plan(BaseModel):
    steps: list[ToolStep]
    overall_reason: str = ""

    @field_validator("steps")
    @classmethod
    def _at_least_one(cls, v: list[ToolStep]) -> list[ToolStep]:
        if not v:
            raise ValueError("plan must have at least one step")
        return v


class PlanTraceStep(BaseModel):
    step_number: int
    tool: str
    args: dict[str, Any]
    reason: str = ""
    output_preview: str = ""
    duration_ms: int = 0
    status: Literal["ok", "error"] = "ok"
    error: Optional[str] = None
