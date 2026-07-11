# multimodal-agent

An agentic app that takes text, images, PDFs, and audio in one request. It
extracts the content, figures out what you want, plans a tool chain,
runs it, and returns a text answer with a visible reasoning trace.

**Live demo:** https://multimodal-agent-w198.onrender.com
**Repo:** https://github.com/nilesh07g/multimodal-agent

> The demo runs on Render's free tier, so it spins down after ~15 minutes of
> no traffic. The first request wakes it up and can take 30-60 seconds.
> After that it responds in a couple of seconds.

---

## What it does

You drop one or more files (image / pdf / audio) into the chat and
optionally type a question. Then:

1. Each file is extracted with a proper tool. Tesseract for image OCR,
   PyMuPDF for PDFs (with Tesseract as a fallback when a PDF page is a
   scan), Groq Whisper for audio.
2. The agent checks if it can understand your goal. If your input is
   ambiguous, it asks a short follow-up question and stops there. If your
   goal is clear it moves on.
3. A planner picks the smallest tool chain that answers your question.
4. An executor runs the chain, one step at a time, and records what
   happened.
5. The UI shows you three panels: the extracted text (collapsible per
   file), the answer (markdown-rendered), and a plan trace with every
   tool that ran, how long it took, and why the planner chose it.

---

## Quickstart

You need Python 3.10 or 3.11.

```bash
git clone https://github.com/nilesh07g/multimodal-agent.git
cd multimodal-agent

# create + activate a virtual env
python -m venv .venv

# windows powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
.\.venv\Scripts\Activate.ps1
# mac / linux
source .venv/bin/activate

# install deps
pip install -r requirements.txt
```

Both API keys are free. No credit card needed.

```bash
# copy the example file and open it in an editor
cp .env.example .env
```

Fill in the two keys:

- `GEMINI_API_KEY` — grab from https://aistudio.google.com/apikey
- `GROQ_API_KEY` — grab from https://console.groq.com/keys

Then run it:

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000 and you're in.

**If you also want to test image OCR and scanned PDFs locally**, you need
two system binaries. The Docker image already has them, so this is only for
local dev:

```powershell
# windows
winget install UB-Mannheim.TesseractOCR
# poppler: grab a release from https://github.com/oschwartz10612/poppler-windows/releases
# extract it and add POPPLER_PATH=C:\poppler\...\bin to your .env
```

On mac or linux, `brew install tesseract poppler` or `apt install
tesseract-ocr poppler-utils` does the same.

---

## Architecture

Three layers, top to bottom.

```
Browser (chat UI — HTML + CSS + vanilla JS + marked for markdown)
        │  multipart POST /api/chat
        ▼
FastAPI  ─── route has a last-mile exception guard so the UI never sees a 500
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ EXTRACTION LAYER  (no LLM here)                          │
│   text        · normalise                                │
│   image_ocr   · Tesseract → text + per-word confidence   │
│   pdf_parser  · PyMuPDF fast path → Tesseract fallback   │
│   audio_stt   · Groq Whisper (whisper-large-v3-turbo)    │
│   url_detector · regex → YouTube + generic URLs          │
└──────────────────────────────────────────────────────────┘
        │  a normalised context dict
        ▼
┌──────────────────────────────────────────────────────────┐
│ AGENT CORE  (Gemini 2.5 Flash Lite for reasoning only)   │
│   1 · clarifier   → "is the goal clear enough to act?"   │
│   2 · planner     → picks tool chain as JSON             │
│   3 · executor    → runs the chain, builds plan_trace    │
│   4 · composer    → formats the final answer             │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ TOOL REGISTRY  (Pydantic in, Pydantic out, every tool)   │
│   summarize · sentiment · code_explain                   │
│   compare_texts · youtube_transcript · conversational    │
└──────────────────────────────────────────────────────────┘
        │
        ▼   { answer, extracted, plan_trace, follow_up? }
UI renders three panels: extracted / answer / plan trace
```

There's a bigger version of this in [`docs/architecture.png`](docs/architecture.png).

### Folder layout

```
app/
├── main.py              FastAPI entry
├── config.py            settings loaded from .env
├── routes/chat.py       POST /api/chat + exception guard
├── extractors/          text · image_ocr · pdf_parser · audio_stt · url_detector
├── agent/               clarifier · planner · executor · orchestrator · context
├── tools/               6 task tools + registry
├── services/            gemini · groq_client (thin retry wrappers)
├── models/schemas.py    Pydantic models for every LLM input and output
├── static/              app.js · style.css
└── templates/index.html chat UI

tests/                   37 tests (23 run offline)
Dockerfile               python:3.11-slim with tesseract-ocr and poppler-utils
render.yaml              Render infra-as-code
```

---

## Why I built it this way

Six things I want to explain, because they were real decisions I had to
make.

### 1. I don't hand every file to a multimodal LLM

Gemini can look at an image, a PDF, or listen to audio. It would have been
the easiest path — one API call handles everything. I picked the harder
path: Tesseract does OCR, PyMuPDF parses PDFs, Groq Whisper transcribes
audio.

Reason: I wanted to *prove I can code*, not just prove I can call an LLM.
If I had one God-tool that swallows every input, there's no interesting
orchestration to talk about. With separate tools the planner is picking
from real, distinct options that each do one job, and the reasoning trace
actually means something.

### 2. No LangChain, no LangGraph

I wrote the orchestrator myself. Each of the four stages
(clarifier / planner / executor / composer) is about 40 lines of Python.
You can read the whole control flow in one sitting. If I imported a
framework I'd save some code, but I'd also hide the part that actually
makes this an "agentic" app.

### 3. Three stages, three prompts

The clarifier, planner, and executor are separate files with separate
prompts. Why:

- Each stage has different **failure modes**. If the clarifier crashes, we
  should probably still try to plan. If the planner returns garbage, we
  should fall back to a plain chat reply. If one tool step fails, the rest
  can still run and we return partial results.
- Each stage has a different **temperature**. Clarifier at 0.0 (I want the
  same input to give the same decision). Planner at 0.1 (nearly
  deterministic). Reasoning tools slightly higher.
- The **must-ask-a-follow-up-when-unclear rule** becomes a **hard
  structural gate**: if `Clarification.needed is True`, the planner
  literally does not run. It's not a soft prompt behaviour that the LLM
  can talk itself out of.

### 4. Every LLM output goes through Pydantic

The planner returns JSON. I `json.loads` it and then build a `Plan` object
with Pydantic. If the JSON is malformed or a field is missing, Pydantic
raises. I catch that and **retry the LLM once with the validation error
appended to the prompt** — the model usually corrects itself.

If it fails the second time, I fall back to a single-step `conversational`
plan. Nothing downstream ever gets to work with a bad dict.

I do the same for the clarifier and for every tool's inputs and outputs.
Boundaries are enforced.

### 5. The plan trace is real, not just a log line

Every response body has a `plan_trace` array. Each entry has step number,
tool name, args, reason, output preview, duration in ms, and status
(`ok` / `err`). The UI has a dedicated collapsible panel that renders it.

I wanted explainability that survives a code review — if something looks
off, you can see exactly which tool got called with which args and how
long it took. Not a black box that says "here's your answer, trust me."

### 6. Rate limits fail fast and get a friendly message

Gemini's free tier is tight. When it 429s, the response includes a
`retryDelay` like 46 seconds. Honouring that is polite but Render's HTTP
proxy times out at 60 seconds. If we sit through the wait, the user gets
a mystery 502.

So I bail immediately on 429, the route-level guard translates it into
*"the language model is rate-limited right now. please try again in a
minute."*, and the trace panel still shows the real 429 error for
debugging. That is what "graceful degradation on bad inputs" looks like
in practice.

---

## Features and where to find them

| Feature | Where it lives |
|---|---|
| Text input | `extractors/text.py` — normalises the raw query |
| Image → OCR | `extractors/image_ocr.py` — Tesseract via `pytesseract.image_to_data`, returns per-word confidence |
| PDF → parse + OCR fallback | `extractors/pdf_parser.py` — PyMuPDF first, per-page Tesseract fallback via `pdf2image` when a page has almost no text |
| Audio → speech-to-text | `extractors/audio_stt.py` — Groq Whisper `whisper-large-v3-turbo` |
| Accept multiple files at once | `/api/chat` iterates every uploaded file and aggregates into one context |
| Intent understanding | `agent/clarifier.py` + `agent/planner.py` |
| Ask a follow-up when the input is ambiguous | Clarifier is a structural gate; UI renders a highlighted "i need a bit more info" bubble; your next reply carries the prior question forward |
| Cross-input reference (URL inside a PDF, etc.) | `url_detector.find_youtube_urls` runs over the merged text; planner sees a `$youtube_url` artifact and chains `youtube_transcript` → `summarize` |
| Summarisation (1-liner + 3 bullets + 5-sentence) | `tools/summarize.py`, validated by `SummarizeResult` |
| Sentiment (label + confidence + justification) | `tools/sentiment.py`, validated by `SentimentResult` |
| Code explanation (bugs + Big-O) | `tools/code_explain.py`, validated by `CodeExplainResult` |
| YouTube transcript fetch | `tools/youtube.py` — `youtube-transcript-api`, gracefully falls back with a message if captions are disabled |
| Cross-input reasoning | `tools/compare_texts.py` — same_topic + similarities + differences + summary |
| Text-only output | UI renders markdown into the answer panel |
| Extracted text panel next to the answer | Collapsible **Extracted** panel per file with OCR confidence, page count, language, duration |
| Reasoning / tool chain view | Collapsible **Plan Trace** panel — step number, tool, ok/err, duration, reason, output preview |
| Public deployment | Live URL at the top of this file |
| Dockerfile + config | `Dockerfile`, `.dockerignore`, `render.yaml` |
| Env var setup docs | `.env.example` + Quickstart above |

---

## Edge cases the app handles

Every case here is covered by a test in
`tests/test_route_api_chat.py` or `tests/test_extractors_edges.py`.

| What went wrong | What the user sees | Under the hood |
|---|---|---|
| Empty POST (no files, no query) | A canned greeting | Route short-circuits before the agent |
| Unsupported MIME (`.exe`, etc.) | Per-file "unsupported file type" | Kind detection returns `None`; file entry gets an `error` string |
| Oversized file | Per-file "file too large" | Size caps in `settings.max_*_bytes` enforced before extraction |
| Empty file | Per-file "empty file" | Bail before hitting the extractor |
| Corrupt PDF | Per-file "could not open pdf" | `pdf_parser.parse` catches PyMuPDF error and wraps in `ValueError` |
| Scanned PDF with no text layer | Falls back to per-page Tesseract OCR | `pdf_ocr_char_threshold` triggers the fallback |
| Gemini rate limit (429) | Friendly "rate-limited, try again" | Fast-fail retry + route guard + trace shows the real 429 |
| Orchestrator crash (any exception) | Same friendly message, trace step marked `err` | Route-level try/except; the UI never sees a 500 |
| Planner returns malformed JSON | Silent retry with schema error appended to prompt; then fallback to `conversational` if still bad | `services/gemini.generate_validated` |
| YouTube video without captions | Tool returns `fallback_used=True` with an explanation; agent moves on to next step | `tools/youtube.py` |

---

## Tests

```bash
# fast, offline (no API keys needed)
pytest tests/test_extractors_edges.py tests/test_route_api_chat.py

# full suite (needs GEMINI_API_KEY in .env)
pytest tests/
```

- **37 tests total.**
- **23 run offline** in about 4 seconds. Corrupt PDFs, oversized files,
  unsupported MIME, URL detection across 5 YouTube URL shapes, text
  normaliser edges, orchestrator crash handling, rate-limit path.
- **14 need `GEMINI_API_KEY`.** One smoke test per tool, plus six
  end-to-end orchestrator runs covering different scenarios (audio →
  summary, PDF + query, image with code, PDF containing a YouTube URL,
  audio + PDF cross-comparison, and one clarifier-triggered ambiguous
  input).
- **2 are skipped automatically** when Tesseract isn't on your `PATH`.

---

## Deployment

Docker + Render, defined in [`render.yaml`](render.yaml).

To deploy your own copy:

1. Fork this repo.
2. Go to https://dashboard.render.com → **New → Blueprint** → connect your fork.
3. When Render prompts you, paste your `GEMINI_API_KEY` and `GROQ_API_KEY`.
4. First Docker build takes 5-10 minutes (it apt-installs Tesseract + Poppler
   and pip-installs everything). Later deploys are much faster because the
   base layers are cached.

The container installs `tesseract-ocr` and `poppler-utils` via `apt`, so
image OCR and scanned-PDF fallback work in production even if you never
installed them locally.

---

## Known limitations

I'd rather flag these than hope nobody notices.

- **Render free tier cold-starts.** After ~15 minutes idle, the first
  request takes 30-60 seconds. Subsequent ones are quick.
- **Gemini free tier is only 20 requests per day per Google project.**
  Each full agent run uses 2-3 requests. About seven full runs will
  exhaust it. When that happens the app doesn't crash — it returns the
  friendly rate-limit message. A fresh Google project gives a fresh
  bucket.
- **PDF hyperlinks stored as link annotations** — where the visible text
  says "click here" but the actual URL lives in a hidden annotation — are
  not extracted right now. Plain-text URLs inside PDFs work fine.
- **Chat sessions live in the browser only.** Refresh and the
  conversation is gone. The follow-up context is carried in the next
  request payload, not stored server-side.

---

## What I'd add with another day

- **`answer_over_context` tool** — a dedicated Q&A tool for "extract just
  the action items from this PDF" style queries, instead of leaning on
  `summarize` or `conversational`.
- **PDF link-annotation extraction** — pull URL destinations from
  PyMuPDF's `page.get_links()` so hidden hyperlinks get picked up too.
- **Cost / token estimator** (bonus item) — every LLM call already goes
  through `services/gemini.py`, so this would be one wrapper.
- **Streaming responses** (bonus item) — swap the single `fetch` in
  `app.js` for Server-Sent Events and render tokens as they arrive.

---

## Stack

- **Backend:** FastAPI, Uvicorn, Pydantic 2, pydantic-settings
- **LLM:** Google Gemini 2.5 Flash Lite via `google-genai`
- **Extraction:** Tesseract (`pytesseract`), PyMuPDF, pdf2image + Poppler, Groq Whisper (`whisper-large-v3-turbo`)
- **Frontend:** vanilla HTML + CSS + JavaScript, Jinja2 template, `marked` for markdown
- **Container:** Docker on `python:3.11-slim`
- **Deployment:** Render web service (free tier)
- **Tests:** pytest, FastAPI TestClient, httpx
