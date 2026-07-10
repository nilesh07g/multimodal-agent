import io

import pytesseract
from PIL import Image

from app.config import settings

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


class TesseractMissingError(RuntimeError):
    pass


def ocr_bytes(data: bytes) -> dict:
    """Run Tesseract on image bytes. Returns {text, avg_confidence, word_count}."""
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        raise ValueError(f"could not open image: {e}")

    try:
        d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as e:
        raise TesseractMissingError(
            "tesseract binary not found. install it and either put it on PATH "
            "or set TESSERACT_CMD in .env"
        ) from e

    words, confs = [], []
    for w, c in zip(d.get("text", []), d.get("conf", [])):
        w = (w or "").strip()
        if not w:
            continue
        try:
            ci = int(float(c))
        except (TypeError, ValueError):
            ci = -1
        if ci < 0:
            continue
        words.append(w)
        confs.append(ci)

    text = " ".join(words)
    avg = round(sum(confs) / len(confs), 2) if confs else 0.0
    return {
        "text": text,
        "avg_confidence": avg,
        "word_count": len(words),
    }
