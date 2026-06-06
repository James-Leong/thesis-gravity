from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent

from app.agents.core.model import TgVisionModel
from app.schemas.analysis import ChecklistBatchResult

INSTRUCTIONS = (
    "You are a thesis visual checklist reviewer. Assess each requested checklist item against the provided thesis page images and text snippets. "
    "Return one assessment per check_id. Use `passed` only when the page images clearly satisfy the requirement. "
    "Use `failed` when the images or text show a concrete violation. Use `needs_manual_review` when the evidence is still insufficient. "
    "Be conservative and mention the relevant page numbers in your rationale."
)


@lru_cache(maxsize=1)
def get_vision_checklist_reviewer_agent() -> Agent:
    return Agent(
        name="VisionChecklistReviewer",
        model=TgVisionModel(),
        instructions=INSTRUCTIONS,
        output_schema=ChecklistBatchResult,
    )
