from datetime import timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.core.constants import (
    ANALYSIS_STATUS_COMPLETED,
    ANALYSIS_STATUS_PENDING,
    MENTOR_RELATION_STATUS_APPROVED,
    THESIS_STATUS_ANALYSIS_PENDING,
    THESIS_STATUS_CHANGES_REQUESTED,
    THESIS_STATUS_MENTOR_REVIEW,
)
from app.core.security import create_access_token, hash_password
from app.db import SessionLocal, init_db
from app.main import app
from app.models import AnalysisTask, MentorRelation, MentorReview, Notification, Thesis, ThesisVersion, User
from app.utils.datetime import utcnow

client = TestClient(app)


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def _reset_db():
    init_db()
    db = SessionLocal()
    db.query(MentorReview).delete()
    db.query(Notification).delete()
    db.query(MentorRelation).delete()
    db.query(AnalysisTask).delete()
    db.query(ThesisVersion).delete()
    db.query(Thesis).delete()
    db.query(User).delete()
    db.commit()
    db.close()


def _create_user(email: str, role: str) -> User:
    db = SessionLocal()
    user = User(email=email, password_hash=hash_password("secret"), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def _create_version(
    thesis: Thesis,
    version_no: int,
    *,
    ready: bool,
    file_path: str = "data/test-version.pdf",
    llm_usage_summary_json: dict | None = None,
    created_at=None,
) -> ThesisVersion:
    db = SessionLocal()
    managed_thesis = db.get(Thesis, thesis.id)
    version = ThesisVersion(
        thesis_id=managed_thesis.id,
        version_no=version_no,
        stage="revision" if version_no > 1 else "draft",
        file_path=file_path,
    )
    db.add(version)
    db.flush()
    task = AnalysisTask(
        version_id=version.id,
        status=ANALYSIS_STATUS_COMPLETED,
        result_json={
            "summary": "测试分析结果",
            "overall_assessment": "整体符合规范",
            "ready_for_mentor": True,
            "issues": [],
            "checks": [],
            "layer_summaries": [],
        },
        llm_usage_summary_json=llm_usage_summary_json,
        student_ready_for_mentor=ready,
        created_at=created_at or utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(version)
    db.close()
    return version


class TestThesisWorkflow:
    def setup_method(self):
        _reset_db()

    def test_submit_draft_appends_new_version_to_existing_thesis(self, monkeypatch):
        monkeypatch.setattr("app.routers.theses.validate_pdf_content", lambda _: None)
        monkeypatch.setattr("app.routers.theses.run_analysis_task", lambda _: None)

        student = _create_user("student@example.com", "student")
        token = create_access_token(str(student.id))

        db = SessionLocal()
        thesis = Thesis(student_id=student.id, title="Old Title", status=THESIS_STATUS_CHANGES_REQUESTED)
        db.add(thesis)
        db.flush()
        version = ThesisVersion(
            thesis_id=thesis.id,
            version_no=1,
            stage="draft",
            file_path="data/existing.pdf",
        )
        db.add(version)
        db.flush()
        task = AnalysisTask(version_id=version.id, status=ANALYSIS_STATUS_COMPLETED)
        db.add(task)
        db.commit()
        thesis_id = thesis.id
        db.close()

        response = client.post(
            "/theses/drafts",
            headers=_auth_headers(token),
            data={"title": "Updated Thesis", "thesis_id": str(thesis_id)},
            files={"file": ("draft.pdf", b"%PDF-1.4 test", "application/pdf")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["thesis_id"] == thesis_id

        db = SessionLocal()
        refreshed = db.get(Thesis, thesis_id)
        versions = (
            db.query(ThesisVersion)
            .filter(ThesisVersion.thesis_id == thesis_id)
            .order_by(ThesisVersion.version_no.asc())
            .all()
        )
        latest_task = (
            db.query(AnalysisTask)
            .filter(AnalysisTask.version_id == versions[-1].id)
            .order_by(AnalysisTask.created_at.desc())
            .first()
        )
        db.close()

        assert refreshed.title == "Updated Thesis"
        assert refreshed.status == THESIS_STATUS_ANALYSIS_PENDING
        assert len(versions) == 2
        assert versions[-1].version_no == 2
        assert versions[-1].stage == "revision"
        assert latest_task is not None
        assert latest_task.status == ANALYSIS_STATUS_PENDING

    def test_submit_draft_rejects_when_thesis_in_mentor_review(self, monkeypatch):
        monkeypatch.setattr("app.routers.theses.validate_pdf_content", lambda _: None)
        monkeypatch.setattr("app.routers.theses.run_analysis_task", lambda _: None)

        student = _create_user("student@example.com", "student")
        token = create_access_token(str(student.id))

        db = SessionLocal()
        thesis = Thesis(student_id=student.id, title="Locked Thesis", status=THESIS_STATUS_MENTOR_REVIEW)
        db.add(thesis)
        db.commit()
        thesis_id = thesis.id
        db.close()

        response = client.post(
            "/theses/drafts",
            headers=_auth_headers(token),
            data={"title": "Locked Thesis", "thesis_id": str(thesis_id)},
            files={"file": ("draft.pdf", b"%PDF-1.4 test", "application/pdf")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "论文正在导师审核中，暂不允许再次提交。"

    def test_pending_reviews_only_returns_latest_version(self):
        student = _create_user("student@example.com", "student")
        mentor = _create_user("mentor@example.com", "mentor")
        token = create_access_token(str(mentor.id))

        db = SessionLocal()
        thesis = Thesis(student_id=student.id, title="Test Thesis", status=THESIS_STATUS_MENTOR_REVIEW)
        db.add(thesis)
        db.flush()
        relation = MentorRelation(
            mentor_id=mentor.id,
            student_id=student.id,
            status=MENTOR_RELATION_STATUS_APPROVED,
        )
        db.add(relation)
        db.commit()
        db.refresh(thesis)
        db.close()

        _create_version(thesis, 1, ready=True)
        latest_version = _create_version(thesis, 2, ready=True)

        response = client.get("/mentor/pending-reviews", headers=_auth_headers(token))

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["version"]["id"] == latest_version.id
        assert payload[0]["version"]["version_no"] == 2

    def test_student_usage_stats_include_all_time_and_current_month(self):
        student = _create_user("student@example.com", "student")
        token = create_access_token(str(student.id))

        db = SessionLocal()
        thesis = Thesis(student_id=student.id, title="Usage Thesis", status=THESIS_STATUS_ANALYSIS_PENDING)
        db.add(thesis)
        db.commit()
        db.refresh(thesis)
        db.close()

        now = utcnow()
        previous_month = (now.replace(day=1) - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

        _create_version(
            thesis,
            1,
            ready=False,
            llm_usage_summary_json={
                "total_calls": 2,
                "completed_calls": 2,
                "failed_calls": 0,
                "total_input_chars": 1000,
                "total_output_chars": 200,
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
                "cache_read_tokens": 40,
                "cache_write_tokens": 0,
                "reasoning_tokens": 0,
                "total_duration_ms": 800,
                "average_duration_ms": 400,
                "estimated_cache_hit_rate": 0.3333,
                "phases": [],
            },
            created_at=previous_month,
        )
        _create_version(
            thesis,
            2,
            ready=False,
            llm_usage_summary_json={
                "total_calls": 3,
                "completed_calls": 3,
                "failed_calls": 0,
                "total_input_chars": 2000,
                "total_output_chars": 300,
                "input_tokens": 180,
                "output_tokens": 45,
                "total_tokens": 225,
                "cache_read_tokens": 60,
                "cache_write_tokens": 10,
                "reasoning_tokens": 5,
                "total_duration_ms": 1200,
                "average_duration_ms": 400,
                "estimated_cache_hit_rate": 0.3333,
                "phases": [],
            },
            created_at=now,
        )

        response = client.get("/theses/usage-stats", headers=_auth_headers(token))

        assert response.status_code == 200
        payload = response.json()
        assert payload["current_month"]["task_count"] == 1
        assert payload["current_month"]["task_with_usage_count"] == 1
        assert payload["current_month"]["total_calls"] == 3
        assert payload["current_month"]["total_tokens"] == 225
        assert payload["all_time"]["task_count"] == 2
        assert payload["all_time"]["task_with_usage_count"] == 2
        assert payload["all_time"]["total_calls"] == 5
        assert payload["all_time"]["total_tokens"] == 375
        assert payload["all_time"]["cache_read_tokens"] == 100
