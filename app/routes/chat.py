import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.agent import orchestrator
from app.config import settings
from app.extractors import audio_stt, image_ocr, pdf_parser, text as text_ext, url_detector

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

IMAGE_MIMES = {"image/jpeg", "image/jpg", "image/png"}
PDF_MIMES = {"application/pdf"}
AUDIO_MIMES = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
               "audio/mp4", "audio/x-m4a", "audio/m4a"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
PDF_EXTS = {".pdf"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a"}


def _kind(mime: str, name: str) -> Optional[str]:
    m = (mime or "").lower()
    n = (name or "").lower()
    ext = "." + n.rsplit(".", 1)[-1] if "." in n else ""
    if m in IMAGE_MIMES or ext in IMAGE_EXTS:
        return "image"
    if m in PDF_MIMES or ext in PDF_EXTS:
        return "pdf"
    if m in AUDIO_MIMES or ext in AUDIO_EXTS:
        return "audio"
    return None


def _cap_for(kind: str) -> int:
    return {
        "image": settings.max_image_bytes,
        "pdf": settings.max_pdf_bytes,
        "audio": settings.max_audio_bytes,
    }[kind]


@router.post("/chat")
async def chat(
    query: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    q = text_ext.normalize(query or "")
    file_results: list[dict] = []
    combined_text_for_urls: list[str] = [q]

    for f in files:
        kind = _kind(f.content_type or "", f.filename or "")
        entry: dict = {
            "filename": f.filename,
            "mime": f.content_type,
            "kind": kind,
        }
        if kind is None:
            entry["error"] = f"unsupported file type ({f.content_type or 'unknown'})"
            file_results.append(entry)
            continue

        data = await f.read()
        if len(data) > _cap_for(kind):
            entry["error"] = f"file too large ({len(data)} bytes, cap {_cap_for(kind)})"
            file_results.append(entry)
            continue
        if not data:
            entry["error"] = "empty file"
            file_results.append(entry)
            continue

        try:
            if kind == "image":
                entry["result"] = image_ocr.ocr_bytes(data)
                combined_text_for_urls.append(entry["result"].get("text", ""))
            elif kind == "pdf":
                entry["result"] = pdf_parser.parse(data)
                combined_text_for_urls.append(entry["result"].get("text", ""))
            elif kind == "audio":
                entry["result"] = audio_stt.transcribe_bytes(data, filename=f.filename or "audio")
                combined_text_for_urls.append(entry["result"].get("text", ""))
        except Exception as e:
            entry["error"] = str(e)

        file_results.append(entry)

    haystack = "\n".join(t for t in combined_text_for_urls if t)
    extracted = {
        "text_from_query": q,
        "files": file_results,
        "urls": url_detector.find_urls(haystack),
        "youtube_urls": url_detector.find_youtube_urls(haystack),
    }

    if not q and not file_results:
        return {
            "query": q,
            "extracted": extracted,
            "answer": "type a question or attach a file (image, pdf, audio) to get started.",
            "follow_up": None,
            "plan": None,
            "plan_trace": [],
        }

    try:
        agent_out = orchestrator.run(q, extracted)
    except Exception as e:
        # last-mile guard: never let the api return a 500. the ui always gets
        # a usable envelope, and the plan_trace surfaces the error.
        log.exception("orchestrator crashed")
        msg = str(e) or type(e).__name__
        friendly = msg
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            friendly = "the language model is rate-limited right now. please try again in a minute."
        agent_out = {
            "answer": friendly,
            "follow_up": None,
            "plan": None,
            "plan_trace": [{
                "step_number": 0,
                "tool": "orchestrator",
                "args": {},
                "reason": "",
                "output_preview": "",
                "duration_ms": 0,
                "status": "error",
                "error": msg[:400],
            }],
        }
    return {"query": q, "extracted": extracted, **agent_out}
