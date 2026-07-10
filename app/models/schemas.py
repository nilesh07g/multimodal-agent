from typing import Literal, Optional

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
