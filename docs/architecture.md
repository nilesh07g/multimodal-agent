# Architecture

This is the long form of what the README summarises. If you want the
three-minute version, read the README. If you want to understand how each
piece talks to the others, keep reading here.

---

## High-level shape

```
Browser (chat UI)
   │  multipart POST /api/chat  (query text + N files)
   ▼
FastAPI routes/chat.py
   │  ── route-level exception guard (no 500 ever reaches the UI)
   ▼
Extraction layer  (per file, no LLM)
   │  text · image_ocr · pdf_parser · audio_stt · url_detector
   ▼
Agent core
   │  clarifier → planner → executor → composer
   ▼
Tool registry  (Pydantic in / Pydantic out)
   │  summarize · sentiment · code_explain · compare_texts
   │  youtube_transcript · conversational
   ▼
Response envelope
   { extracted, answer, follow_up, plan, plan_trace }
```

Three layers, each with a single job:

- **Extraction** turns raw bytes into typed text. No LLM here on purpose.
- **Agent core** is the brain. Three prompts, three responsibilities, one shared context.
- **Tool registry** is the hands. Every tool is a pure function with a Pydantic input and a Pydantic output.

---

## Request lifecycle

Here's what happens when a request lands on `/api/chat`.

### 1. Route entry (`routes/chat.py`)

```python
@router.post("/chat")
async def chat(query: str = Form(""), files: list[UploadFile] = File(default=[])):
    q = text_ext.normalize(query)
    file_results = []

    for f in files:
        kind = _kind(f.content_type, f.filename)   # image | pdf | audio | None
        ...run size caps + extractor...
        file_results.append(entry)

    extracted = {
        "text_from_query": q,
        "files": file_results,
        "urls": url_detector.find_urls(haystack),
        "youtube_urls": url_detector.find_youtube_urls(haystack),
    }

    if not q and not file_results:
        return short_circuit_greeting()

    try:
        agent_out = orchestrator.run(q, extracted)
    except Exception as e:
        agent_out = friendly_error_envelope(e)   # 429s get a specific msg
    return {"query": q, "extracted": extracted, **agent_out}
```

The `try/except` around `orchestrator.run` is the **last-mile guard**.
Anything that escapes the agent — rate limits, transient network errors,
a bug I didn't catch — becomes a 200 response with an error entry in the
plan trace. The UI never sees a 500.

### 2. Extraction (`app/extractors/`)

Each file is dispatched based on its MIME type / extension:

| Kind | Extractor | Backing library |
|---|---|---|
| image | `image_ocr.ocr_bytes` | Tesseract via `pytesseract.image_to_data` — returns text + average per-word confidence + word count |
| pdf | `pdf_parser.parse` | PyMuPDF (`fitz`) for text pages, `pdf2image` + Tesseract for scanned pages under the char threshold |
| audio | `audio_stt.transcribe_bytes` | Groq Whisper (`whisper-large-v3-turbo`) — returns text + language + duration |

The `url_detector` runs regex over the merged text (query + every
extracted transcript / PDF text / OCR result) and returns YouTube URLs
with `video_id` separated from generic URLs.

### 3. Agent orchestrator (`app/agent/orchestrator.py`)

Four stages, each in its own file.

```
extracted context
        │
        ▼
    clarifier         (temperature 0.0)
        │
        ├── needed=True  ───► return { follow_up: "..." }  (planner never runs)
        │
        ▼ needed=False
    planner           (temperature 0.1, JSON output validated as Plan)
        │
        ▼
    executor          (runs each ToolStep, threads $prev between steps)
        │
        ▼
    composer          (formats the last successful step into markdown)
        │
        ▼
    { answer, follow_up=None, plan, plan_trace }
```

**Clarifier** returns:

```python
class Clarification(BaseModel):
    needed: bool
    question: str | None
```

If `needed=True`, we short-circuit and hand `question` to the UI. This is
the **hard structural gate** — the planner literally cannot run.

**Planner** returns:

```python
class ToolStep(BaseModel):
    tool: str
    args: dict[str, Any]
    reason: str

class Plan(BaseModel):
    steps: list[ToolStep]
    overall_reason: str
```

If the JSON is malformed or the schema is wrong, we **retry the LLM once
with the validation error appended to the prompt**. If it fails again we
fall back to `Plan(steps=[ToolStep(tool="conversational", ...)])`.

**Executor** iterates steps. For each step:

1. Look up the tool in the registry.
2. Resolve `$artifact` references in `args` (e.g. `$audio_text`, `$pdf_text`, `$youtube_url`, `$prev`).
3. Call the tool.
4. Append to `plan_trace` with duration + status + output preview.

Every step is wrapped in `try/except` — one failed step doesn't kill the
run. Failed steps get `status="error"` and the next step still runs.

**Composer** looks at the last successful step and formats its result
into a markdown answer.

### 4. Tool registry (`app/tools/registry.py`)

```python
REGISTRY: dict[str, Tool] = {
    "summarize":         Tool(...),
    "sentiment":         Tool(...),
    "code_explain":      Tool(...),
    "compare_texts":     Tool(...),
    "youtube_transcript":Tool(...),   # no LLM, uses youtube-transcript-api
    "conversational":    Tool(...),
}
```

Each Gemini-backed tool is a small function with:

1. A purpose-specific system prompt (10-20 lines).
2. A user prompt template.
3. A call to `services.gemini.generate_validated(prompt, ResultModel)`.

The result model does the same **JSON-loads → Pydantic → retry-once-with-error → fallback** dance.

---

## Data flow example — "PDF with a YouTube URL, summarise the video"

This is the cross-input reasoning case.

```
1. Browser POSTs the PDF + query "summarise the youtube video in this pdf"

2. Extractors run:
     pdf_parser.parse(bytes)  →  { text: "...watch: https://youtu.be/xxx...", pages: [...] }
     url_detector.find_youtube_urls(text)  →  [{ url: "...", video_id: "xxx" }]

3. Orchestrator builds a context artifact map:
     {
       "$query": "summarise the youtube video in this pdf",
       "$pdf_text": "...watch: https://youtu.be/xxx...",
       "$youtube_url": "https://youtu.be/xxx",
       ...
     }

4. Clarifier sees a clear intent → needed=False.

5. Planner is told the artifacts. It returns:
     Plan(steps=[
       ToolStep(tool="youtube_transcript", args={"source": "$youtube_url"}, reason="fetch the transcript"),
       ToolStep(tool="summarize",         args={"context": "$prev"},        reason="1-liner + bullets + 5-sentence"),
     ])

6. Executor runs step 1:
     - resolves $youtube_url  →  "https://youtu.be/xxx"
     - calls tools.youtube.run("https://youtu.be/xxx")
     - stores result.transcript
     - plan_trace[0] = { tool: "youtube_transcript", status: "ok", duration_ms: 1200, ... }

7. Executor runs step 2:
     - $prev  →  step-1 transcript
     - calls tools.summarize.run(context=transcript)
     - plan_trace[1] = { tool: "summarize", status: "ok", duration_ms: 2340, ... }

8. Composer formats step 2's SummarizeResult into markdown.

9. Response envelope goes back to the UI:
     {
       extracted: { files: [{filename: "notes.pdf", ...}], youtube_urls: [...] },
       answer: "**one-liner** ... **3 bullets** ... **5-sentence summary** ...",
       follow_up: null,
       plan: {...},
       plan_trace: [step1, step2],
     }
```

---

## The Pydantic models (`app/models/schemas.py`)

Every LLM I/O boundary has a model. This is deliberate — I never trust an
LLM to return well-shaped JSON without validating it first.

- Tool result models: `SummarizeResult`, `SentimentResult`, `CodeExplainResult`, `CompareResult`, `YoutubeResult`, `ConversationalResult`.
- Agent models: `Clarification`, `ToolStep`, `Plan`, `PlanTraceStep`.
- Extractor models: informal `TypedDict`-like shapes (I kept these as plain dicts to reduce ceremony where the boundary isn't LLM-facing).

---

## Failure paths

Where each kind of failure gets caught and what the user sees.

```
File-level failures (bad MIME, oversize, empty, corrupt)
  → per-file `error` string in extracted.files[i].error
  → agent still runs on the other files
  → response is 200

Extractor-level unexpected exception
  → caught in routes/chat.py inside the per-file try/except
  → same as above, per-file error entry

Clarifier crash or invalid JSON
  → orchestrator falls through to planner (act rather than block)
  → logged, but not user-visible

Planner crash (rate limit / network)
  → propagates to route-level guard
  → guard returns friendly message + trace entry with real error

Planner returns invalid JSON
  → services.gemini.generate_validated retries once with schema error
  → if still invalid, falls back to single-step conversational Plan

Executor step crash
  → the step's plan_trace entry gets status="error"
  → the rest of the plan continues running
  → composer works with whatever partial results survived

Rate limit (429) anywhere in the agent
  → fast-fail (no long retryDelay wait — Render's proxy would time out)
  → route guard returns "the language model is rate-limited right now"
  → trace shows the underlying 429 for debugging
```

---

## Deployment topology

```
        ┌────────────────┐
        │  User browser  │
        └───────┬────────┘
                │  HTTPS
                ▼
       ┌────────────────────┐
       │  Render edge (CDN) │
       └────────┬───────────┘
                │
                ▼
       ┌────────────────────────────┐
       │  Docker container          │
       │  python:3.11-slim          │
       │  + tesseract-ocr           │
       │  + poppler-utils           │
       │  uvicorn app.main:app      │
       │  binds $PORT (Render sets) │
       └──┬─────────────────────┬───┘
          │                     │
          ▼                     ▼
   Google Gemini API      Groq API (Whisper)
```

- Render builds the Dockerfile on push (auto-deploy on `main`).
- Env vars (`GEMINI_API_KEY`, `GROQ_API_KEY`) live in Render's dashboard, not in git.
- The container is stateless — no local disk writes matter across requests.
- Free tier spins down after 15 minutes of no traffic; a cold start is ~30-60 seconds.

---

## Exporting the diagram as PNG

If you want the boxed diagram at the top of this file as an image
(`docs/architecture.png`) for the README:

1. Open https://excalidraw.com in a new tab.
2. Copy the ASCII diagram from the "High-level shape" section into
   Excalidraw (or redraw it as boxes and arrows — Excalidraw has a
   library of arrow / box shapes).
3. Once it looks the way you want, click **Menu → Export image → PNG**.
4. Save as `docs/architecture.png` in this repo.
5. Commit and push.
