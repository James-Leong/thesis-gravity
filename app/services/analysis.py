from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.agents.draft_reviewer import get_draft_reviewer_agent
from app.core.config import settings
from app.core.constants import (
    ANALYSIS_STATUS_COMPLETED,
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_RUNNING,
    THESIS_STATUS_ANALYSIS_DONE,
)
from app.db import SessionLocal
from app.models import AnalysisTask, Notification
from app.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return settings.base_dir / path


def _load_reference_text() -> str:
    path = settings.reference_doc_path
    if not path.exists():
        return ""
    if path.suffix.lower() not in {".md", ".txt"}:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    total_pages = min(len(reader.pages), settings.max_pages)
    pages: list[tuple[int, str]] = []

    for index in range(total_pages):
        text = (reader.pages[index].extract_text() or "").strip()
        if not text:
            text = "(no extractable text)"
        if settings.max_page_chars and len(text) > settings.max_page_chars:
            text = text[: settings.max_page_chars].rstrip() + "..."
        pages.append((index + 1, text))

    return pages


def _build_prompt(reference_text: str, pages: list[tuple[int, str]]) -> str:
    parts: list[str] = [
        "Review the thesis draft against the reference guidelines.",
        "Report issues with page numbers, severity, and actionable suggestions.",
        "If there are no issues, return an empty issues list and explain why.",
    ]

    if reference_text:
        parts.append("Reference guidelines:\n" + reference_text)

    draft_chunks = [f"Page {page_num}:\n{text}" for page_num, text in pages]
    parts.append("Draft pages:\n" + "\n\n".join(draft_chunks))

    return "\n\n".join(parts)


def analyze_pdf(file_path: str) -> AnalysisResult:
    pdf_path = _resolve_path(file_path)
    pages = _extract_pdf_pages(pdf_path)
    if not pages:
        raise ValueError("No extractable pages found in the PDF.")

    reference_text = _load_reference_text()
    prompt = _build_prompt(reference_text, pages)

    agent = get_draft_reviewer_agent()
    response = agent.run(prompt)
    content = response.content

    if isinstance(content, AnalysisResult):
        return content
    return AnalysisResult.model_validate(content)


def _to_user_facing_error(exc: Exception) -> str:
    message = str(exc)
    if "OPENAI_API_KEY not set" in message:
        return "本次分析暂未完成，请稍后重试。"
    if isinstance(exc, FileNotFoundError):
        return "未找到论文文件，请重新上传后再试。"
    if isinstance(exc, (PdfReadError, ValueError)):
        return "论文文件无法正常解析，请确认上传的是可读取的 PDF。"
    return "本次分析暂未完成，请稍后重试。"


def run_analysis_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        task = db.get(AnalysisTask, task_id)
        if not task:
            return

        task.status = ANALYSIS_STATUS_RUNNING
        task.started_at = datetime.now(timezone.utc)
        db.commit()

        version = task.version
        if not version:
            raise RuntimeError("Missing thesis version for analysis task.")

        result = analyze_pdf(version.file_path)
        task.result_json = result.model_dump()
        task.status = ANALYSIS_STATUS_COMPLETED
        task.finished_at = datetime.now(timezone.utc)

        thesis = version.thesis
        if thesis:
            thesis.status = THESIS_STATUS_ANALYSIS_DONE

            notification = Notification(
                user_id=thesis.student_id,
                title="Draft review completed",
                body="Your draft review is ready in the system.",
                is_read=False,
            )
            db.add(notification)

        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Analysis task %s failed", task_id)
        task = db.get(AnalysisTask, task_id)
        if task:
            task.status = ANALYSIS_STATUS_FAILED
            task.error_message = _to_user_facing_error(exc)
            task.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
