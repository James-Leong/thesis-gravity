from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.thesis import AnalysisTaskRead


class MentorReviewCreate(BaseModel):
    version_id: int
    decision: str = Field(..., pattern="^(approved|changes_requested)$")
    comments: str | None = None


class MentorReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_id: int
    mentor_id: int
    decision: str
    comments: str | None = None
    created_at: datetime


class MentorUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None = None


class MentorVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_no: int
    stage: str
    file_path: str
    submitted_at: datetime


class MentorThesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    student: MentorUserRead


class MentorPendingReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: MentorVersionRead
    thesis: MentorThesisRead
    latest_task: AnalysisTaskRead


class MentorTrackedThesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thesis: MentorThesisRead
    current_version: MentorVersionRead
    latest_task: AnalysisTaskRead | None = None
    latest_review: MentorReviewRead | None = None


class MentorVersionDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: MentorVersionRead
    thesis: MentorThesisRead
    latest_task: AnalysisTaskRead | None = None
    reviews: list[MentorReviewRead]


class MentorReviewSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review: MentorReviewRead
    thesis: MentorThesisRead
    version: MentorVersionRead


class MentorRelationCreate(BaseModel):
    mentor_id: int


class MentorRelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mentor_id: int
    student_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class MentorListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None = None


class MentorStudentRead(BaseModel):
    """导师视角的已绑定学生"""

    id: int
    email: str
    name: str | None = None
    thesis_count: int = 0
    bound_at: datetime


class MentorStudentListRead(BaseModel):
    total: int
    items: list[MentorStudentRead]


class StudentApplicationRead(BaseModel):
    """学生视角的申请状态"""

    has_application: bool
    application: MentorRelationRead | None = None
    mentor: MentorListRead | None = None


class MentorApplicationRead(BaseModel):
    """导师视角的申请"""

    application: MentorRelationRead
    student: MentorListRead
