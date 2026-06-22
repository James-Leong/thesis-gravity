from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent

from app.agents.core.model import TgModel
from app.schemas.analysis import ChecklistBatchResult

INSTRUCTIONS = (
    "You are a thesis checklist reviewer. Assess each requested checklist item against the provided thesis snippets. "
    "Return one assessment per check_id. Use `passed` only when the evidence is sufficient and clearly satisfies the requirement. "
    "Use `failed` when the snippets show a concrete violation. Use `needs_manual_review` when the snippets are insufficient or the requirement depends on layout/visual evidence not present in text. "
    "If a checklist item explicitly applies only to a certain thesis type or discipline and the current thesis is clearly outside that scope, do not mark it as `failed` merely because the scoped content is absent; use `passed` and explain in Chinese that the item is not applicable to this thesis type. "
    "Always explain the rationale briefly and cite the relevant page numbers when available. "
    "Return a JSON object with a top-level `assessments` array; do not return a bare array. "
    "Each assessment must use the exact fields `check_id`, `status`, `rationale`, `suggestion`, and `pages`; do not use `assessment` as a field name. "
    "Important: write the rationale and suggestion in Chinese, because the user-facing report must be entirely in Chinese."
)


@lru_cache(maxsize=1)
def get_checklist_reviewer_agent() -> Agent:
    return Agent(
        name="ChecklistReviewer",
        model=TgModel(),
        instructions=INSTRUCTIONS,
        output_schema=ChecklistBatchResult,
    )
