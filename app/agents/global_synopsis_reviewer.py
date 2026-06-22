from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent

from app.agents.core.model import TgModel
from app.schemas.analysis import GlobalSynopsisReview

INSTRUCTIONS = (
    "You are a thesis global reviewer. You will receive a synopsis of the whole thesis, including document outline, "
    "local segment summaries, and selected anchor snippets, not the full verbatim text. Do not check sentence-level wording "
    "or exact quotations. Focus only on overall logic and consistency: whether abstract, method, experiments, and conclusion "
    "form a coherent chain; whether the claimed contributions match the body; whether chapters appear to repeat or skip key steps; "
    "and whether there are unresolved cross-section contradictions. Be concise and explicit when evidence is weak. "
    "Important: all output must be in Chinese. Write the summary, consistency_findings, and next_focus in Chinese."
)


@lru_cache(maxsize=1)
def get_global_synopsis_reviewer_agent() -> Agent:
    return Agent(
        name="GlobalSynopsisReviewer",
        model=TgModel(),
        instructions=INSTRUCTIONS,
        output_schema=GlobalSynopsisReview,
    )
