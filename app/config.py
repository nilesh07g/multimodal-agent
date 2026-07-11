from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_PATH), extra="ignore")

    gemini_api_key: str = ""
    groq_api_key: str = ""

    gemini_model: str = "gemini-flash-latest"
    whisper_model: str = "whisper-large-v3-turbo"

    # upload caps (bytes)
    max_image_bytes: int = 10 * 1024 * 1024
    max_pdf_bytes: int = 20 * 1024 * 1024
    max_audio_bytes: int = 25 * 1024 * 1024

    # pdf: if a page yields less than this many chars via PyMuPDF, fall back to OCR
    pdf_ocr_char_threshold: int = 40

    # optional overrides for system binaries (windows installs often not on PATH)
    tesseract_cmd: str = ""
    poppler_path: str = ""


settings = Settings()
