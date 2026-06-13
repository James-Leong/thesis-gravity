from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import AnalysisLLMUsageSummary, AnalysisResult


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
    thesis_id: int | None = None
    version_id: int | None = None
    thesis_title: str | None = None
    status: str
    result: AnalysisResult | None = None
    llm_usage_summary: AnalysisLLMUsageSummary | None = None
    error_message: str | None = None
    student_ready_for_mentor: bool = False
    ignored_issue_keys: list[str] | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ThesisVersionTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_no: int
    stage: str
    file_path: str
    submitted_at: datetime
    latest_task: AnalysisTaskRead | None = None


class ThesisWorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    current_version: ThesisVersionTaskRead | None = None
    versions: list[ThesisVersionTaskRead]


class StudentUsagePeriodRead(BaseModel):
    period_start: datetime | None = None
    period_end: datetime | None = None
    task_count: int = Field(default=0, ge=0)
    task_with_usage_count: int = Field(default=0, ge=0)
    total_calls: int = Field(default=0, ge=0)
    completed_calls: int = Field(default=0, ge=0)
    failed_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_duration_ms: int = Field(default=0, ge=0)


class StudentUsageStatsRead(BaseModel):
    generated_at: datetime
    current_month: StudentUsagePeriodRead
    all_time: StudentUsagePeriodRead


class DraftSubmissionResponse(BaseModel):
    thesis_id: int
    version_id: int
    task: AnalysisTaskRead
