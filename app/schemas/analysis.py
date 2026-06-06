from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., ge=1)
    page_label: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    issue_type: str
    severity: str
    description: str
    suggestion: str


class AnalysisCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    title: str
    source_section: str
    requirement: str
    layer: Literal["rule", "text_model", "vision_model"]
    severity: Literal["low", "medium", "high"]
    status: Literal["passed", "failed", "needs_manual_review"]
    rationale: str
    suggestion: str
    pages: list[int] = Field(default_factory=list)
    page_labels: list[str] = Field(default_factory=list)
    pdf_pages: list[int] = Field(default_factory=list)


class AnalysisLayerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: Literal["rule", "text_model", "vision_model"]
    total: int = Field(..., ge=0)
    passed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    needs_manual_review: int = Field(..., ge=0)


class AnalysisLLMUsagePhaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: str
    calls: int = Field(..., ge=0)
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    cache_read_tokens: int = Field(..., ge=0)
    total_duration_ms: int = Field(..., ge=0)


class AnalysisLLMUsageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_calls: int = Field(default=0, ge=0)
    completed_calls: int = Field(default=0, ge=0)
    failed_calls: int = Field(default=0, ge=0)
    total_input_chars: int = Field(default=0, ge=0)
    total_output_chars: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_duration_ms: int = Field(default=0, ge=0)
    average_duration_ms: int = Field(default=0, ge=0)
    estimated_cache_hit_rate: float | None = None
    phases: list[AnalysisLLMUsagePhaseSummary] = Field(default_factory=list)


class ChecklistAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    status: Literal["passed", "failed", "needs_manual_review"]
    rationale: str
    suggestion: str
    pages: list[int] = Field(default_factory=list)


class ChecklistBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessments: list[ChecklistAssessment] = Field(default_factory=list)


class LocalSegmentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    major_topics: list[str] = Field(default_factory=list)
    logic_risks: list[str] = Field(default_factory=list)


class GlobalSynopsisReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    consistency_findings: list[str] = Field(default_factory=list)
    next_focus: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    global_summary: str | None = None
    visual_summary: str | None = None
    issues: list[AnalysisIssue] = Field(default_factory=list)
    checks: list[AnalysisCheck] = Field(default_factory=list)
    layer_summaries: list[AnalysisLayerSummary] = Field(default_factory=list)
    llm_usage_summary: AnalysisLLMUsageSummary | None = None
    overall_assessment: str
    ready_for_mentor: bool
