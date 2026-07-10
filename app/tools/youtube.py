from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from app.extractors.url_detector import find_youtube_urls
from app.models.schemas import YoutubeResult

DESCRIPTION = (
    "Fetch the transcript of a YouTube video from a URL or video_id. Use when "
    "the content contains a YouTube link and the user wants its contents, "
    "summary, or transcription. Returns a graceful fallback message if the "
    "video has no captions."
)


def _extract_video_id(query_or_url: str) -> tuple[str, str]:
    """Return (video_id, source_url). Raises ValueError if we can't find one."""
    hits = find_youtube_urls(query_or_url)
    if hits:
        return hits[0]["video_id"], hits[0]["url"]
    # allow bare 11-char id
    s = query_or_url.strip()
    if len(s) == 11 and all(c.isalnum() or c in "-_" for c in s):
        return s, f"https://youtu.be/{s}"
    raise ValueError("no youtube url or video_id found")


def run(source: str) -> dict:
    video_id, url = _extract_video_id(source)
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        text = " ".join(s.text for s in fetched.snippets).strip()
        if not text:
            raise NoTranscriptFound(video_id, ["en"], None)
        result = YoutubeResult(
            transcript=text,
            source_url=url,
            video_id=video_id,
            fallback_used=False,
        )
        return result.model_dump()
    except TranscriptsDisabled:
        note = "captions are disabled on this video"
    except NoTranscriptFound:
        note = "no transcript available for this video"
    except VideoUnavailable:
        note = "video is unavailable or private"
    except Exception as e:
        note = f"transcript fetch failed: {e}"

    result = YoutubeResult(
        transcript="",
        source_url=url,
        video_id=video_id,
        fallback_used=True,
        note=note,
    )
    return result.model_dump()
