from typing import Optional

import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError

from app.config import settings


def parse(data: bytes) -> dict:
    """Parse PDF: PyMuPDF text extraction, OCR fallback for scanned pages."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ValueError(f"could not open pdf: {e}")

    total = doc.page_count
    pages_info: list[Optional[dict]] = [None] * total
    page_texts: list[str] = [""] * total
    ocr_needed: list[int] = []

    for i in range(total):
        try:
            page = doc.load_page(i)
            txt = page.get_text().strip()
        except Exception:
            txt = ""
        if len(txt) >= settings.pdf_ocr_char_threshold:
            page_texts[i] = txt
            pages_info[i] = {"page": i + 1, "method": "text", "char_count": len(txt)}
        else:
            ocr_needed.append(i)

    doc.close()

    if ocr_needed:
        _ocr_pages(data, ocr_needed, page_texts, pages_info)

    # any page still without info at this point is empty
    for i in range(total):
        if pages_info[i] is None:
            pages_info[i] = {"page": i + 1, "method": "empty", "char_count": 0}

    combined = "\n\n".join(t for t in page_texts if t)
    ocr_count = sum(1 for p in pages_info if p and p.get("method") == "ocr")

    return {
        "text": combined,
        "pages": pages_info,
        "total_pages": total,
        "ocr_pages": ocr_count,
    }


def _ocr_pages(data: bytes, indices: list[int], page_texts: list[str], pages_info: list[Optional[dict]]) -> None:
    try:
        kwargs = {"dpi": 200, "fmt": "png"}
        if settings.poppler_path:
            kwargs["poppler_path"] = settings.poppler_path
        images = convert_from_bytes(data, **kwargs)
    except (PDFInfoNotInstalledError, PDFPageCountError):
        for i in indices:
            pages_info[i] = {"page": i + 1, "method": "empty", "char_count": 0,
                             "note": "poppler missing, install it or set POPPLER_PATH"}
        return
    except Exception as e:
        for i in indices:
            pages_info[i] = {"page": i + 1, "method": "empty", "char_count": 0,
                             "note": f"pdf render error: {e}"}
        return

    for i in indices:
        if i >= len(images):
            pages_info[i] = {"page": i + 1, "method": "empty", "char_count": 0}
            continue
        img = images[i]
        try:
            text = pytesseract.image_to_string(img).strip()
            data_dict = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confs = []
            for c in data_dict.get("conf", []):
                try:
                    ci = int(float(c))
                except (TypeError, ValueError):
                    ci = -1
                if ci >= 0:
                    confs.append(ci)
            avg = round(sum(confs) / len(confs), 2) if confs else 0.0
            page_texts[i] = text
            pages_info[i] = {
                "page": i + 1,
                "method": "ocr",
                "char_count": len(text),
                "avg_confidence": avg,
            }
        except pytesseract.TesseractNotFoundError:
            pages_info[i] = {"page": i + 1, "method": "empty", "char_count": 0,
                             "note": "tesseract missing"}
        except Exception as e:
            pages_info[i] = {"page": i + 1, "method": "empty", "char_count": 0,
                             "note": f"ocr error: {e}"}
