from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent
from agno.models.openai.like import OpenAILike

from app.core.config import settings
from app.schemas.analysis import AnalysisResult

INSTRUCTIONS = (
    "You are a thesis review assistant. Compare the draft against the reference "
    "guidelines and identify concrete issues. Provide page numbers, concise "
    "descriptions, and actionable suggestions. If the draft is mostly clean, "
    "return an empty issues list and explain why."
)


def _build_model():
    if settings.llm_base_url:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required when LLM_BASE_URL is set.")
        return OpenAILike(
            id=settings.llm_model_id,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return f"{settings.llm_provider}:{settings.llm_model_id}"


@lru_cache(maxsize=1)
def get_draft_reviewer_agent() -> Agent:
    return Agent(
        name="DraftReviewer",
        model=_build_model(),
        instructions=INSTRUCTIONS,
        output_schema=AnalysisResult,
    )
