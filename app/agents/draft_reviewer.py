from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent

from app.agents.core.model import TgModel
from app.schemas.analysis import AnalysisResult

INSTRUCTIONS = (
    "You are a thesis review assistant. Compare the draft against the reference "
    "guidelines and identify concrete issues. Provide page numbers, concise "
    "descriptions, and actionable suggestions. If the draft is mostly clean, "
    "return an empty issues list and explain why."
)


@lru_cache(maxsize=1)
def get_draft_reviewer_agent() -> Agent:
    return Agent(
        name="DraftReviewer",
        model=TgModel(),
        instructions=INSTRUCTIONS,
        output_schema=AnalysisResult,
    )
