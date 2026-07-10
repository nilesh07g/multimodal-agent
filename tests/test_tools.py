"""Smoke tests for phase 3 tools. Require GEMINI_API_KEY in .env (skipped otherwise)."""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set; skipping tool smoke tests",
)

from app.tools import (  # noqa: E402
    code_explain,
    compare_texts,
    conversational,
    sentiment,
    summarize,
    youtube,
)


def test_summarize_shape():
    r = summarize.run("The quick brown fox jumps over the lazy dog. This is a common pangram used in typing practice.")
    assert isinstance(r["one_liner"], str) and r["one_liner"]
    assert isinstance(r["bullets"], list) and len(r["bullets"]) >= 2
    assert isinstance(r["five_sentence"], str) and r["five_sentence"]


def test_sentiment_shape():
    r = sentiment.run("I absolutely loved this movie, best I've seen all year.")
    assert r["label"] in {"positive", "negative", "neutral", "mixed"}
    assert 0.0 <= r["confidence"] <= 1.0
    assert isinstance(r["justification"], str) and r["justification"]


def test_code_explain_shape():
    code = "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n - 1)"
    r = code_explain.run(code)
    assert isinstance(r["explanation"], str) and r["explanation"]
    assert isinstance(r["bugs"], list)
    assert isinstance(r["time_complexity"], str) and r["time_complexity"]


def test_compare_texts_shape():
    a = "Python is a dynamically typed interpreted language popular for data science."
    b = "Python is widely used in machine learning, offering libraries like NumPy and PyTorch."
    r = compare_texts.run(a, b)
    assert isinstance(r["same_topic"], bool)
    assert isinstance(r["similarities"], list)
    assert isinstance(r["differences"], list)
    assert isinstance(r["summary"], str) and r["summary"]


def test_conversational_shape():
    r = conversational.run("Say hello in one short sentence.")
    assert isinstance(r["reply"], str) and r["reply"]


def test_youtube_bad_id_graceful():
    # invalid id must not raise — should return fallback
    r = youtube.run("https://youtu.be/aaaaaaaaaaa")
    assert r["fallback_used"] is True
    assert isinstance(r["note"], str) and r["note"]
