from pydantic import BaseModel, ConfigDict, Field


class AnalysisIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., ge=1)
    issue_type: str
    severity: str
    description: str
    suggestion: str


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    issues: list[AnalysisIssue] = Field(default_factory=list)
    overall_assessment: str
    ready_for_mentor: bool
