"""Turn the raw extraction dict into named artifacts the planner + executor share.

The planner references artifacts by name (e.g. "$pdf_text", "$audio_text",
"$youtube_url", "$prev"). The executor substitutes those names for actual
values before invoking each tool. Keeps big text out of the planner's JSON.
"""
from typing import Any


AVAILABLE_ARTIFACTS = [
    "$query",         # the user's typed query
    "$extracted_all", # concatenation of all extracted text
    "$pdf_text",      # first PDF's extracted text
    "$audio_text",    # first audio's transcript
    "$image_text",    # first image's OCR text
    "$youtube_url",   # first YouTube URL found
    "$prev",          # previous step's primary output text (executor injects at run time)
]


def build(query: str, extracted: dict[str, Any]) -> dict[str, Any]:
    """Flatten extraction into named artifacts + a human-readable summary."""
    pdf_texts, audio_texts, image_texts = [], [], []

    for f in extracted.get("files", []) or []:
        if "error" in f:
            continue
        kind = f.get("kind")
        res = f.get("result") or {}
        text = (res.get("text") or "").strip()
        if kind == "pdf" and text:
            pdf_texts.append(text)
        elif kind == "audio" and text:
            audio_texts.append(text)
        elif kind == "image" and text:
            image_texts.append(text)

    yt = extracted.get("youtube_urls") or []
    youtube_url = yt[0]["url"] if yt else ""

    all_bits = []
    if query:
        all_bits.append(f"[query] {query}")
    for i, t in enumerate(pdf_texts):
        all_bits.append(f"[pdf {i+1}]\n{t}")
    for i, t in enumerate(audio_texts):
        all_bits.append(f"[audio {i+1}]\n{t}")
    for i, t in enumerate(image_texts):
        all_bits.append(f"[image {i+1}]\n{t}")

    return {
        "$query": query or "",
        "$extracted_all": "\n\n".join(all_bits).strip(),
        "$pdf_text": pdf_texts[0] if pdf_texts else "",
        "$audio_text": audio_texts[0] if audio_texts else "",
        "$image_text": image_texts[0] if image_texts else "",
        "$youtube_url": youtube_url,
        # $prev filled in by executor as steps run
    }


def summarize_for_planner(query: str, extracted: dict[str, Any], artifacts: dict[str, Any]) -> str:
    """One-paragraph description of what's available. Feeds the planner + clarifier prompts."""
    lines = []
    lines.append(f'user query: "{query}"' if query else "user query: (empty)")

    files = extracted.get("files", []) or []
    if not files:
        lines.append("no files uploaded")
    else:
        counts = {"pdf": 0, "audio": 0, "image": 0, "other": 0, "error": 0}
        for f in files:
            if "error" in f:
                counts["error"] += 1
            else:
                counts[f.get("kind") or "other"] = counts.get(f.get("kind") or "other", 0) + 1
        parts = [f"{n} {k}" for k, n in counts.items() if n]
        lines.append("uploads: " + ", ".join(parts))

    yt = extracted.get("youtube_urls") or []
    if yt:
        lines.append(f"youtube urls detected: {len(yt)} (first: {yt[0]['url']})")

    # short preview of first bit of extracted text
    preview = (artifacts.get("$extracted_all") or "")[:400]
    if preview:
        lines.append(f"extracted preview:\n{preview}")

    return "\n".join(lines)
