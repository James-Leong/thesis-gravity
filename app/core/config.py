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

        self.reference_doc_path = Path(
            _getenv(
                "REFERENCE_DOC_PATH",
                str(self.base_dir / "source" / "common-problems-for-students.md"),
            )
        )
        self.max_pages = int(_getenv("MAX_PAGES", "30"))
        self.max_page_chars = int(_getenv("MAX_PAGE_CHARS", "4000"))
        self.cors_origins = _csv(_getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"))
        self.log_level = _getenv("LOG_LEVEL", "DEBUG")


settings = Settings()
