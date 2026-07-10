import re

# youtube in all common shapes: watch?v=, youtu.be, shorts, embed, live
_YT_PATTERNS = [
    re.compile(r"https?://(?:www\.)?youtube\.com/watch\?[^\s]*v=([\w-]{11})", re.I),
    re.compile(r"https?://youtu\.be/([\w-]{11})", re.I),
    re.compile(r"https?://(?:www\.)?youtube\.com/shorts/([\w-]{11})", re.I),
    re.compile(r"https?://(?:www\.)?youtube\.com/embed/([\w-]{11})", re.I),
    re.compile(r"https?://(?:www\.)?youtube\.com/live/([\w-]{11})", re.I),
]

_GENERIC_URL = re.compile(r"https?://[^\s<>\"'`]+", re.I)


def find_youtube_urls(text: str) -> list[dict]:
    """Return list of {url, video_id} for each YouTube URL found."""
    if not text:
        return []
    hits: list[dict] = []
    seen: set[str] = set()
    for pat in _YT_PATTERNS:
        for m in pat.finditer(text):
            url = m.group(0)
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            hits.append({"url": url, "video_id": vid})
    return hits


def find_urls(text: str) -> list[str]:
    if not text:
        return []
    urls = _GENERIC_URL.findall(text)
    # dedupe preserving order
    out, seen = [], set()
    for u in urls:
        # strip trailing punctuation that regex tends to grab
        u = u.rstrip(".,);]")
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out
