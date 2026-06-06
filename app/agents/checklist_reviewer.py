from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent

from app.agents.core.model import TgModel
from app.schemas.analysis import ChecklistBatchResult

INSTRUCTIONS = (
    "You are a thesis checklist reviewer. Assess each requested checklist item against the provided thesis snippets. "
    "Return one assessment per check_id. Use `passed` only when the evidence is sufficient and clearly satisfies the requirement. "
    "Use `failed` when the snippets show a concrete violation. Use `needs_manual_review` when the snippets are insufficient or the requirement depends on layout/visual evidence not present in text. "
    "Always explain the rationale briefly and cite the relevant page numbers when available."
)


@lru_cache(maxsize=1)
def get_checklist_reviewer_agent() -> Agent:
    return Agent(
        name="ChecklistReviewer",
        model=TgModel(),
        instructions=INSTRUCTIONS,
        output_schema=ChecklistBatchResult,
    )
