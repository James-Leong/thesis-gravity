from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ROLE_STUDENT
from app.db import Base
from app.utils.datetime import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default=ROLE_STUDENT, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    theses: Mapped[list[Thesis]] = relationship(back_populates="student")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")


class Thesis(Base):
    __tablename__ = "theses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    student: Mapped[User] = relationship(back_populates="theses")
    versions: Mapped[list[ThesisVersion]] = relationship(
        back_populates="thesis",
        cascade="all, delete-orphan",
    )


class ThesisVersion(Base):
    __tablename__ = "thesis_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    thesis_id: Mapped[int] = mapped_column(ForeignKey("theses.id"), index=True, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    thesis: Mapped[Thesis] = relationship(back_populates="versions")
    analysis_tasks: Mapped[list[AnalysisTask]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
    )
    mentor_reviews: Mapped[list[MentorReview]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
    )


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("thesis_versions.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_usage_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_ready_for_mentor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ignored_issue_keys_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    version: Mapped[ThesisVersion] = relationship(back_populates="analysis_tasks")
    llm_call_logs: Mapped[list[AnalysisLLMCallLog]] = relationship(
        back_populates="analysis_task",
        cascade="all, delete-orphan",
    )


class AnalysisLLMCallLog(Base):
    __tablename__ = "analysis_llm_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"), index=True, nullable=False)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    call_index: Mapped[int] = mapped_column(Integer, nullable=False)
    request_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_prefix_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_prefix_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_to_first_token_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_ids_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    page_numbers_json: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    analysis_task: Mapped[AnalysisTask] = relationship(back_populates="llm_call_logs")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="notifications")


class MentorReview(Base):
    __tablename__ = "mentor_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("thesis_versions.id"), index=True, nullable=False)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    version: Mapped[ThesisVersion] = relationship(back_populates="mentor_reviews")


class MentorRelation(Base):
    __tablename__ = "mentor_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
