from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    groq_api_key: str = ""

    gemini_model: str = "gemini-2.5-flash"
    whisper_model: str = "whisper-large-v3-turbo"

    # upload caps (bytes)
    max_image_bytes: int = 10 * 1024 * 1024
    max_pdf_bytes: int = 20 * 1024 * 1024
    max_audio_bytes: int = 25 * 1024 * 1024

    # pdf: if a page yields less than this many chars via PyMuPDF, fall back to OCR
    pdf_ocr_char_threshold: int = 40


settings = Settings()
