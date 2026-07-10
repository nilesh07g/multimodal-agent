"""Agent smoke tests. Exercise orchestrator against synthetic extraction outputs
that mimic each of the assignment's sample cases.

Requires GEMINI_API_KEY in .env. Skipped otherwise.
"""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set; skipping agent tests",
)

from app.agent import orchestrator  # noqa: E402


def _extracted(files=None, urls=None, youtube_urls=None, query=""):
    return {
        "text_from_query": query,
        "files": files or [],
        "urls": urls or [],
        "youtube_urls": youtube_urls or [],
    }


def _file(kind: str, text: str, filename: str = "sample"):
    return {
        "filename": filename,
        "mime": f"{kind}/x",
        "kind": kind,
        "result": {"text": text},
    }


# ---------- case 1: audio -> summary ----------
def test_audio_only_summarize():
    audio_text = (
        "Today's lecture covered gradient descent. We started with the intuition of "
        "walking downhill on a loss surface, then formalised it as an update rule. "
        "We saw how learning rate affects convergence: too small is slow, too large "
        "overshoots. We touched on momentum and Adam as popular improvements."
    )
    q = "summarise this"
    out = orchestrator.run(q, _extracted(files=[_file("audio", audio_text, "lecture.mp3")], query=q))

    assert out["follow_up"] is None
    assert out["plan"] is not None
    assert out["plan"]["steps"], "expected at least one planned step"
    tools = [s["tool"] for s in out["plan"]["steps"]]
    assert "summarize" in tools
    assert isinstance(out["answer"], str) and len(out["answer"]) > 20
    assert all(t["status"] == "ok" for t in out["plan_trace"])


# ---------- case 2: pdf + query -> action items ----------
def test_pdf_query_action_items():
    pdf_text = (
        "Meeting notes 10/07/2026.\n"
        "Attendees: alice, bob.\n"
        "Action items:\n"
        "1. Alice to draft the api spec by friday.\n"
        "2. Bob to review the ci pipeline.\n"
        "3. Both to sync on tuesday for a demo."
    )
    q = "what are the action items?"
    out = orchestrator.run(q, _extracted(files=[_file("pdf", pdf_text, "notes.pdf")], query=q))

    assert out["follow_up"] is None
    assert out["plan"] is not None
    assert isinstance(out["answer"], str) and out["answer"]


# ---------- case 3: image with code -> explain ----------
def test_image_code_explain():
    code = "def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)"
    q = "explain this code"
    out = orchestrator.run(q, _extracted(files=[_file("image", code, "code.png")], query=q))

    assert out["follow_up"] is None
    tools = [s["tool"] for s in out["plan"]["steps"]]
    assert "code_explain" in tools
    assert isinstance(out["answer"], str)
    assert "complexity" in out["answer"].lower() or "recursive" in out["answer"].lower()


# ---------- case 4: pdf with youtube url -> transcript + summary ----------
# uses a known TED video with captions
_TED_URL = "https://www.youtube.com/watch?v=8jPQjjsBbIc"
_TED_ID = "8jPQjjsBbIc"


def test_pdf_with_youtube_chain():
    pdf_text = f"See the reference video: {_TED_URL}\nRead this before the meeting."
    q = "hit the yt url in this pdf and give me a summary of it"
    extracted = _extracted(
        files=[_file("pdf", pdf_text, "brief.pdf")],
        urls=[_TED_URL],
        youtube_urls=[{"url": _TED_URL, "video_id": _TED_ID}],
        query=q,
    )
    out = orchestrator.run(q, extracted)

    assert out["follow_up"] is None
    tools = [s["tool"] for s in out["plan"]["steps"]]
    # planner should chain youtube_transcript then summarize
    assert "youtube_transcript" in tools
    # answer should be non-empty even if youtube fails (fallback path)
    assert isinstance(out["answer"], str) and out["answer"]


# ---------- case 5: audio + pdf compare ----------
def test_audio_pdf_compare():
    pdf_text = "This document discusses climate policy, focusing on renewable energy subsidies."
    audio_text = "In today's talk we cover machine learning fundamentals: gradient descent, backpropagation."
    q = "do the audio and the document discuss the same topic?"
    out = orchestrator.run(q, _extracted(
        files=[_file("pdf", pdf_text, "climate.pdf"), _file("audio", audio_text, "ml.mp3")],
        query=q,
    ))

    assert out["follow_up"] is None
    tools = [s["tool"] for s in out["plan"]["steps"]]
    assert "compare_texts" in tools
    assert isinstance(out["answer"], str) and "topic" in out["answer"].lower()


# ---------- clarifier: ambiguous input ----------
def test_clarifier_triggers_on_bare_help():
    out = orchestrator.run("?", _extracted(files=[], query="?"))
    # very ambiguous input SHOULD trigger a follow-up. If model returns needed=false, we still
    # want a non-empty answer at minimum.
    if out["follow_up"]:
        assert isinstance(out["follow_up"], str) and len(out["follow_up"]) > 0
    else:
        assert isinstance(out["answer"], str) and out["answer"]
