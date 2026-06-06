from __future__ import annotations

from functools import lru_cache

from agno.agent import Agent

from app.agents.core.model import TgModel
from app.schemas.analysis import LocalSegmentReview

INSTRUCTIONS = (
    "You are a thesis segment reviewer. You will receive one local segment of a thesis as excerpted page snippets, "
    "not the complete thesis. Do not nitpick wording, punctuation, or line-level phrasing. "
    "Focus on the local section logic: whether the segment has a clear purpose, whether arguments and evidence connect, "
    "whether concepts are left undefined, whether there are abrupt jumps or repeated discussion, and whether the segment "
    "appears to complete its intended subtask. Be concise and conservative."
)


@lru_cache(maxsize=1)
def get_local_segment_reviewer_agent() -> Agent:
    return Agent(
        name="LocalSegmentReviewer",
        model=TgModel(),
        instructions=INSTRUCTIONS,
        output_schema=LocalSegmentReview,
    )
