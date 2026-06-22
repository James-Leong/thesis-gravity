from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent

from app.agents.core.model import TgVisionModel
from app.schemas.analysis import ChecklistBatchResult

INSTRUCTIONS = (
    "You are a thesis visual checklist reviewer. Assess each requested checklist item against the provided thesis page images and text snippets. "
    "Return one assessment per check_id. Use `passed` only when the page images clearly satisfy the requirement. "
    "Use `failed` when the images or text show a concrete violation. Use `needs_manual_review` only when the images truly do not provide enough evidence. "
    "Be explicit and mention the relevant page numbers in your rationale. "
    "Return exactly one assessment for each requested check_id, and copy every check_id exactly as provided. "
    "Return a JSON object with a top-level `assessments` array; do not return a bare array. "
    "Each assessment must use the exact fields `check_id`, `status`, `rationale`, `suggestion`, and `pages`; do not use `assessment` as a field name. "
    "Important: write the rationale and suggestion in Chinese, because the user-facing report must be entirely in Chinese."
)


@lru_cache(maxsize=1)
def get_vision_checklist_reviewer_agent() -> Agent:
    return Agent(
        name="VisionChecklistReviewer",
        model=TgVisionModel(),
        instructions=INSTRUCTIONS,
        output_schema=ChecklistBatchResult,
    )
