from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.analysis import AnalysisResult


class ThesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class AnalysisTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    result: AnalysisResult | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DraftSubmissionResponse(BaseModel):
    thesis_id: int
    version_id: int
    task: AnalysisTaskRead
