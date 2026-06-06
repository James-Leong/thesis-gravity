from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


def _getenv(key: str, default: str) -> str:
    return os.getenv(key, default)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings:
    def __init__(self) -> None:
        load_dotenv()
        self.base_dir = Path(_getenv("APP_BASE_DIR", str(BASE_DIR)))
        self.app_name = _getenv("APP_NAME", "Thesis Guidance")
        self.data_dir = Path(_getenv("DATA_DIR", str(self.base_dir / "data")))
        self.database_url = _getenv(
            "DATABASE_URL",
            f"sqlite:///{self.data_dir / 'app.db'}",
        )
        self.jwt_secret_key = _getenv("JWT_SECRET_KEY", "change-me")
        self.jwt_algorithm = _getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(_getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
        self.session_cookie_name = _getenv("SESSION_COOKIE_NAME", "tg_session")
        self.session_cookie_secure = _bool(_getenv("SESSION_COOKIE_SECURE", "false"))
        self.session_cookie_samesite: Literal["lax", "strict", "none"] = _getenv(
            "SESSION_COOKIE_SAMESITE", "strict"
        ).lower()  # type: ignore[assignment]

        self.llm_provider = _getenv("LLM_PROVIDER", "openai")
        self.llm_model_id = _getenv("LLM_MODEL_ID", "gpt-4o-mini")
        self.llm_api_key = _getenv("LLM_API_KEY", _getenv("OPENAI_API_KEY", ""))
        self.llm_base_url = _getenv("LLM_BASE_URL", _getenv("OPENAI_BASE_URL", ""))
        self.vision_llm_provider = _getenv("VISION_LLM_PROVIDER", self.llm_provider)
        self.vision_llm_model_id = _getenv("VISION_LLM_MODEL_ID", "")
        self.vision_llm_api_key = _getenv(
            "VISION_LLM_API_KEY",
            _getenv("VISION_OPENAI_API_KEY", self.llm_api_key),
        )
        self.vision_llm_base_url = _getenv(
            "VISION_LLM_BASE_URL",
            _getenv("VISION_OPENAI_BASE_URL", self.llm_base_url),
        )
        self.max_check_items_per_batch = int(_getenv("MAX_CHECK_ITEMS_PER_BATCH", "64"))
        self.max_pages_per_check = int(_getenv("MAX_PAGES_PER_CHECK", "6"))
        self.max_page_image_candidates = int(_getenv("MAX_PAGE_IMAGE_CANDIDATES", "4"))
        self.max_pages_per_batch = int(_getenv("MAX_PAGES_PER_BATCH", "12"))
        self.max_image_pages_per_batch = int(_getenv("MAX_IMAGE_PAGES_PER_BATCH", "8"))
        self.local_review_page_batch_size = int(_getenv("LOCAL_REVIEW_PAGE_BATCH_SIZE", "30"))
        self.segment_review_page_chars = int(_getenv("SEGMENT_REVIEW_PAGE_CHARS", "2000"))
        self.global_anchor_page_chars = int(_getenv("GLOBAL_ANCHOR_PAGE_CHARS", "500"))

        self.reference_doc_path = Path(
            _getenv(
                "REFERENCE_DOC_PATH",
                str(self.base_dir / "source" / "common-problems-for-students.md"),
            )
        )
        self.max_pages = int(_getenv("MAX_PAGES", "120"))
        self.max_page_chars = int(_getenv("MAX_PAGE_CHARS", "4000"))
        self.cors_origins = _csv(_getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"))
        self.log_level = _getenv("LOG_LEVEL", "DEBUG")
        self.log_to_console = _bool(_getenv("LOG_TO_CONSOLE", "false"))
        self.environment = _getenv("ENV", "development").lower()

    def is_dev(self) -> bool:
        return self.environment in {"development", "dev"}


settings = Settings()
