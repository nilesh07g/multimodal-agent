"""Shared pytest fixtures. Everything generated in-memory, no binary files in git."""
import io
import struct
import wave

import fitz  # PyMuPDF
import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """A tiny valid text PDF with a couple lines PyMuPDF can extract."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello world from a test pdf")
    page.insert_text((72, 96), "second line for good measure")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def sample_png_bytes() -> bytes:
    """A small white PNG with some text drawn on it. Tesseract may or may not
    be installed — extractor code should handle both."""
    img = Image.new("RGB", (400, 100), "white")
    draw = ImageDraw.Draw(img)
    # default PIL font is tiny but readable
    draw.text((10, 40), "sample text for ocr test", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_wav_bytes() -> bytes:
    """0.5 seconds of silence @ 16kHz mono. Valid wav header + PCM."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<8000h", *([0] * 8000)))
    return buf.getvalue()


@pytest.fixture
def corrupt_pdf_bytes() -> bytes:
    return b"%PDF-1.4 this is not a real pdf just garbage bytes 12345"


@pytest.fixture
def empty_bytes() -> bytes:
    return b""
