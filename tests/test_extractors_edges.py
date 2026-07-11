"""Edge-case coverage for the extraction layer. No api keys needed for most of these."""
import shutil

import pytest

from app.extractors import pdf_parser, text as text_ext, url_detector


# ---------- pdf ----------
def test_pdf_valid(sample_pdf_bytes):
    out = pdf_parser.parse(sample_pdf_bytes)
    assert out["total_pages"] == 1
    assert "hello world" in out["text"].lower()
    assert out["pages"][0]["method"] == "text"


def test_pdf_corrupt_raises(corrupt_pdf_bytes):
    with pytest.raises(ValueError):
        pdf_parser.parse(corrupt_pdf_bytes)


def test_pdf_empty_raises(empty_bytes):
    with pytest.raises(ValueError):
        pdf_parser.parse(empty_bytes)


# ---------- text normalizer ----------
def test_text_normalize_collapses_newlines():
    out = text_ext.normalize("line one\n\n\n\nline two")
    assert out == "line one\n\nline two"


def test_text_normalize_collapses_spaces():
    out = text_ext.normalize("hello     world")
    assert out == "hello world"


def test_text_normalize_empty():
    assert text_ext.normalize("") == ""
    assert text_ext.normalize(None) == ""


def test_text_normalize_handles_crlf():
    assert text_ext.normalize("a\r\nb\r\nc") == "a\nb\nc"


# ---------- url detector ----------
def test_youtube_url_watch_form():
    yt = url_detector.find_youtube_urls("see https://www.youtube.com/watch?v=abc123XYZ_-")
    assert len(yt) == 1
    assert yt[0]["video_id"] == "abc123XYZ_-"


def test_youtube_url_short_form():
    yt = url_detector.find_youtube_urls("check https://youtu.be/dQw4w9WgXcQ now")
    assert yt[0]["video_id"] == "dQw4w9WgXcQ"


def test_youtube_url_shorts_form():
    yt = url_detector.find_youtube_urls("https://youtube.com/shorts/aBc123defGh")
    assert yt[0]["video_id"] == "aBc123defGh"


def test_no_urls_returns_empty():
    assert url_detector.find_urls("nothing to see here") == []
    assert url_detector.find_youtube_urls("nothing to see here") == []


def test_generic_urls_not_youtube():
    urls = url_detector.find_urls("visit https://example.com and https://docs.python.org")
    assert "https://example.com" in urls
    assert "https://docs.python.org" in urls
    assert url_detector.find_youtube_urls("visit https://example.com") == []


# ---------- image ocr (skipped if tesseract missing) ----------
_HAS_TESSERACT = shutil.which("tesseract") is not None


@pytest.mark.skipif(not _HAS_TESSERACT, reason="tesseract binary not installed")
def test_image_ocr_valid(sample_png_bytes):
    from app.extractors import image_ocr
    out = image_ocr.ocr_bytes(sample_png_bytes)
    assert "text" in out
    assert isinstance(out["text"], str)
    assert "avg_confidence" in out


@pytest.mark.skipif(not _HAS_TESSERACT, reason="tesseract binary not installed")
def test_image_ocr_empty_raises(empty_bytes):
    from app.extractors import image_ocr
    with pytest.raises(ValueError):
        image_ocr.ocr_bytes(empty_bytes)


# ---------- audio duration rounding ----------
def test_audio_duration_rounds_to_one_decimal():
    from app.extractors import audio_stt
    # patch groq_client so we don't hit the network
    import types
    fake_result = {"text": "hi", "language": "en", "duration": 18.356187136}
    original = audio_stt.groq_client.transcribe
    audio_stt.groq_client.transcribe = lambda data, filename=None: fake_result
    try:
        out = audio_stt.transcribe_bytes(b"x", filename="fake.wav")
    finally:
        audio_stt.groq_client.transcribe = original
    assert out["duration_sec"] == 18.4  # 18.356... rounds to 18.4
