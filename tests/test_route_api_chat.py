"""Integration tests for /api/chat covering the robustness paths.
No live API calls — orchestrator is monkey-patched where LLM would be hit."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ---------- helpers ----------
def _fake_agent_out(answer: str = "stub", **extra):
    base = {
        "answer": answer,
        "follow_up": None,
        "plan": {"steps": [{"tool": "conversational", "args": {}, "reason": "test"}],
                 "overall_reason": "test"},
        "plan_trace": [{
            "step_number": 1, "tool": "conversational", "args": {}, "reason": "test",
            "output_preview": answer, "duration_ms": 5, "status": "ok",
        }],
    }
    base.update(extra)
    return base


@pytest.fixture
def stub_orchestrator(monkeypatch):
    """Patch orchestrator.run so route tests don't hit real LLM apis."""
    from app.routes import chat as chat_route
    calls = []

    def fake_run(q, extracted):
        calls.append({"q": q, "extracted": extracted})
        return _fake_agent_out(answer=f"stub reply to: {q}")

    monkeypatch.setattr(chat_route.orchestrator, "run", fake_run)
    return calls


# ---------- empty ----------
def test_empty_post_returns_greeting_no_llm_call(stub_orchestrator):
    r = client.post("/api/chat", data={})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"].startswith("type a question")
    assert body["plan"] is None
    assert stub_orchestrator == []  # llm was NOT called


# ---------- text query ----------
def test_text_only_hits_agent(stub_orchestrator):
    r = client.post("/api/chat", data={"query": "hello"})
    assert r.status_code == 200
    body = r.json()
    assert "stub reply to: hello" in body["answer"]
    assert len(stub_orchestrator) == 1


# ---------- url detection through the route ----------
def test_url_detection_in_route(stub_orchestrator):
    r = client.post("/api/chat", data={"query": "watch https://youtu.be/aBcDeFgHiJk please"})
    body = r.json()
    yts = body["extracted"]["youtube_urls"]
    assert len(yts) == 1
    assert yts[0]["video_id"] == "aBcDeFgHiJk"


# ---------- unsupported file type ----------
def test_unsupported_mime_returns_per_file_error(stub_orchestrator):
    r = client.post(
        "/api/chat",
        data={"query": "read this"},
        files={"files": ("evil.exe", b"MZ\x90\x00binary junk", "application/octet-stream")},
    )
    assert r.status_code == 200
    files = r.json()["extracted"]["files"]
    assert len(files) == 1
    assert "unsupported" in files[0]["error"]


# ---------- corrupt pdf ----------
def test_corrupt_pdf_returns_per_file_error(stub_orchestrator, corrupt_pdf_bytes):
    r = client.post(
        "/api/chat",
        data={"query": "summarise"},
        files={"files": ("junk.pdf", corrupt_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200
    files = r.json()["extracted"]["files"]
    assert "error" in files[0]
    assert "pdf" in files[0]["error"].lower()


# ---------- valid pdf gets extracted ----------
def test_valid_pdf_extraction(stub_orchestrator, sample_pdf_bytes):
    r = client.post(
        "/api/chat",
        data={"query": "summarise"},
        files={"files": ("notes.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200
    files = r.json()["extracted"]["files"]
    assert "error" not in files[0]
    assert "hello world" in files[0]["result"]["text"].lower()


# ---------- oversized file ----------
def test_oversized_pdf_rejected(monkeypatch, stub_orchestrator):
    from app.config import settings
    monkeypatch.setattr(settings, "max_pdf_bytes", 100)  # comically small cap
    big_pdf = b"%PDF-1.4" + b"x" * 500
    r = client.post(
        "/api/chat",
        data={"query": "read"},
        files={"files": ("big.pdf", big_pdf, "application/pdf")},
    )
    assert r.status_code == 200
    err = r.json()["extracted"]["files"][0]["error"]
    assert "too large" in err.lower()


# ---------- empty upload ----------
def test_empty_upload_rejected(stub_orchestrator):
    r = client.post(
        "/api/chat",
        data={"query": "read"},
        files={"files": ("empty.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 200
    err = r.json()["extracted"]["files"][0]["error"]
    assert "empty" in err.lower()


# ---------- orchestrator crash caught by guard ----------
def test_orchestrator_crash_returns_200_not_500(monkeypatch):
    from app.routes import chat as chat_route

    def boom(q, extracted):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(chat_route.orchestrator, "run", boom)
    r = client.post("/api/chat", data={"query": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["plan_trace"][0]["status"] == "error"
    assert "simulated failure" in body["plan_trace"][0]["error"]


# ---------- rate-limit gets friendly message ----------
def test_rate_limit_gets_friendly_message(monkeypatch):
    from app.routes import chat as chat_route

    def rate_limited(q, extracted):
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")

    monkeypatch.setattr(chat_route.orchestrator, "run", rate_limited)
    r = client.post("/api/chat", data={"query": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert "rate-limited" in body["answer"].lower()
