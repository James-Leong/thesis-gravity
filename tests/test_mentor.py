import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.core.constants import (
    MENTOR_RELATION_STATUS_APPROVED,
    MENTOR_RELATION_STATUS_PENDING,
    MENTOR_RELATION_STATUS_REJECTED,
    THESIS_STATUS_ANALYSIS_DONE,
    THESIS_STATUS_APPROVED,
    THESIS_STATUS_CHANGES_REQUESTED,
    THESIS_STATUS_MENTOR_REVIEW,
)
from app.db import SessionLocal, init_db
from app.main import app
from app.models import AnalysisTask, MentorRelation, MentorReview, Notification, Thesis, ThesisVersion, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
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
    yield


@pytest.fixture
def student_user():
    db = SessionLocal()
    user = User(email="student@example.com", password_hash=hash_password("secret"), role="student")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def student_user2():
    db = SessionLocal()
    user = User(email="student2@example.com", password_hash=hash_password("secret"), role="student")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def mentor_user():
    db = SessionLocal()
    user = User(email="mentor@example.com", password_hash=hash_password("secret"), role="mentor")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def mentor_user2():
    db = SessionLocal()
    user = User(email="mentor2@example.com", password_hash=hash_password("secret"), role="mentor")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def admin_user():
    db = SessionLocal()
    user = User(email="admin@example.com", password_hash=hash_password("secret"), role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def mentor_token(mentor_user):
    return create_access_token(str(mentor_user.id))


@pytest.fixture
def student_token(student_user):
    return create_access_token(str(student_user.id))


@pytest.fixture
def student_token2(student_user2):
    return create_access_token(str(student_user2.id))


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(str(admin_user.id))


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def _bind_mentor_student(mentor_id: int, student_id: int, status: str = MENTOR_RELATION_STATUS_APPROVED):
    db = SessionLocal()
    rel = MentorRelation(mentor_id=mentor_id, student_id=student_id, status=status)
    db.add(rel)
    db.commit()
    db.refresh(rel)
    db.close()
    return rel


def _create_ready_version(student_user, status=THESIS_STATUS_MENTOR_REVIEW, ready=True):
    db = SessionLocal()
    thesis = Thesis(student_id=student_user.id, title="Test Thesis", status=status)
    db.add(thesis)
    db.flush()
    version = ThesisVersion(thesis_id=thesis.id, version_no=1, stage="draft", file_path="/tmp/test.pdf")
    db.add(version)
    db.flush()
    task = AnalysisTask(
        version_id=version.id,
        status="completed",
        result_json={
            "summary": "测试分析结果",
            "overall_assessment": "整体符合规范",
            "ready_for_mentor": True,
            "issues": [],
            "checks": [],
            "layer_summaries": [],
        },
        student_ready_for_mentor=ready,
    )
    db.add(task)
    db.commit()
    version_id = version.id
    db.close()
    return version_id


# ── Mentor: list mentors ─────────────────────────────────────


class TestMentorList:
    def test_student_can_list_mentors(self, student_token, mentor_user, mentor_user2):
        response = client.get("/mentor/list", headers=_auth_headers(student_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        assert any(m["email"] == "mentor@example.com" for m in data)

    def test_mentor_cannot_list_mentors(self, mentor_token):
        response = client.get("/mentor/list", headers=_auth_headers(mentor_token))
        assert response.status_code == 403

    def test_unauthenticated_cannot_list(self):
        response = client.get("/mentor/list")
        assert response.status_code == 401


# ── Student: applications ─────────────────────────────────────


class TestStudentApplications:
    def test_create_application(self, student_token, mentor_user):
        response = client.post(
            "/mentor/applications",
            headers=_auth_headers(student_token),
            json={"mentor_id": mentor_user.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mentor_id"] == mentor_user.id
        assert data["status"] == "pending"

    def test_create_application_mentor_not_found(self, student_token):
        response = client.post(
            "/mentor/applications",
            headers=_auth_headers(student_token),
            json={"mentor_id": 99999},
        )
        assert response.status_code == 404

    def test_duplicate_application(self, student_token, student_user, mentor_user):
        _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.post(
            "/mentor/applications",
            headers=_auth_headers(student_token),
            json={"mentor_id": mentor_user.id},
        )
        assert response.status_code == 400

    def test_cannot_apply_when_approved(self, student_token, student_user, mentor_user, mentor_user2):
        _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_APPROVED)
        response = client.post(
            "/mentor/applications",
            headers=_auth_headers(student_token),
            json={"mentor_id": mentor_user2.id},
        )
        assert response.status_code == 400

    def test_reapply_after_rejection(self, student_token, student_user, mentor_user, mentor_user2):
        _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_REJECTED)
        response = client.post(
            "/mentor/applications",
            headers=_auth_headers(student_token),
            json={"mentor_id": mentor_user2.id},
        )
        assert response.status_code == 200
        assert response.json()["mentor_id"] == mentor_user2.id
        assert response.json()["status"] == "pending"

    def test_my_application_empty(self, student_token):
        response = client.get("/mentor/my-application", headers=_auth_headers(student_token))
        assert response.status_code == 200
        assert response.json()["has_application"] is False

    def test_my_application_pending(self, student_token, student_user, mentor_user):
        _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.get("/mentor/my-application", headers=_auth_headers(student_token))
        assert response.status_code == 200
        data = response.json()
        assert data["has_application"] is True
        assert data["application"]["status"] == "pending"
        assert data["mentor"]["email"] == "mentor@example.com"


# ── Mentor: approve / reject ──────────────────────────────────


class TestMentorApplicationHandling:
    def test_list_applications(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.get("/mentor/applications", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["student"]["email"] == "student@example.com"

    def test_list_applications_empty(self, mentor_token):
        response = client.get("/mentor/applications", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        assert response.json() == []

    def test_approve_application(self, mentor_token, mentor_user, student_user):
        rel = _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.post(
            f"/mentor/applications/{rel.id}/approve",
            headers=_auth_headers(mentor_token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    def test_reject_application(self, mentor_token, mentor_user, student_user):
        rel = _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.post(
            f"/mentor/applications/{rel.id}/reject",
            headers=_auth_headers(mentor_token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    def test_approve_already_processed(self, mentor_token, mentor_user, student_user):
        rel = _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_APPROVED)
        response = client.post(
            f"/mentor/applications/{rel.id}/approve",
            headers=_auth_headers(mentor_token),
        )
        assert response.status_code == 400

    def test_cannot_approve_other_mentor_application(self, mentor_token, mentor_user2, student_user):
        rel = _bind_mentor_student(mentor_user2.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.post(
            f"/mentor/applications/{rel.id}/approve",
            headers=_auth_headers(mentor_token),
        )
        assert response.status_code == 404

    def test_student_cannot_approve(self, student_token, mentor_user, student_user):
        rel = _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.post(
            f"/mentor/applications/{rel.id}/approve",
            headers=_auth_headers(student_token),
        )
        assert response.status_code == 403


class TestMentorStudentList:
    def test_list_students(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_APPROVED)
        response = client.get("/mentor/students", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["email"] == "student@example.com"

    def test_list_students_empty(self, mentor_token):
        response = client.get("/mentor/students", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_students_excludes_pending(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id, MENTOR_RELATION_STATUS_PENDING)
        response = client.get("/mentor/students", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


# ── Reviews (with binding) ────────────────────────────────────


class TestMentorPendingReviews:
    def test_list_pending_reviews_as_mentor(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        _create_ready_version(student_user)
        response = client.get("/mentor/pending-reviews", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["thesis"]["title"] == "Test Thesis"

    def test_list_pending_reviews_as_student_forbidden(self, student_token, student_user):
        response = client.get("/mentor/pending-reviews", headers=_auth_headers(student_token))
        assert response.status_code == 403

    def test_pending_reviews_excludes_not_ready(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        _create_ready_version(student_user, ready=False)
        response = client.get("/mentor/pending-reviews", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        assert response.json() == []

    def test_pending_reviews_excludes_non_mentor_status(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        _create_ready_version(student_user, status=THESIS_STATUS_ANALYSIS_DONE)
        response = client.get("/mentor/pending-reviews", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        assert response.json() == []

    def test_pending_reviews_excludes_unbound_student(self, mentor_token, student_user):
        _create_ready_version(student_user)
        response = client.get("/mentor/pending-reviews", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        assert response.json() == []


class TestMentorVersionDetail:
    def test_get_version_detail(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user)
        response = client.get(f"/mentor/versions/{version_id}", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        data = response.json()
        assert data["version"]["id"] == version_id
        assert data["thesis"]["title"] == "Test Thesis"
        assert data["latest_task"]["status"] == "completed"

    def test_get_version_detail_not_found(self, mentor_token):
        response = client.get("/mentor/versions/99999", headers=_auth_headers(mentor_token))
        assert response.status_code == 404


class TestMentorTrackedTheses:
    def test_list_tracked_theses_for_bound_student(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user, status=THESIS_STATUS_CHANGES_REQUESTED)

        response = client.get("/mentor/theses", headers=_auth_headers(mentor_token))

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["thesis"]["title"] == "Test Thesis"
        assert data[0]["thesis"]["status"] == THESIS_STATUS_CHANGES_REQUESTED
        assert data[0]["current_version"]["id"] == version_id
        assert data[0]["latest_task"]["status"] == "completed"

    def test_list_tracked_theses_supports_search(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        _create_ready_version(student_user, status=THESIS_STATUS_CHANGES_REQUESTED)

        response = client.get("/mentor/theses?q=student@example.com", headers=_auth_headers(mentor_token))

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_tracked_theses_excludes_unbound_student(self, mentor_token, student_user):
        _create_ready_version(student_user, status=THESIS_STATUS_CHANGES_REQUESTED)

        response = client.get("/mentor/theses", headers=_auth_headers(mentor_token))

        assert response.status_code == 200
        assert response.json() == []


class TestMentorReviewSubmission:
    def test_approve_review(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user)
        response = client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "approved", "comments": "Good work."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["review"]["decision"] == "approved"
        assert data["thesis"]["status"] == THESIS_STATUS_APPROVED
        assert data["version"]["stage"] == "final"

    def test_request_changes_review(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user)
        response = client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "changes_requested", "comments": "Fix it."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["review"]["decision"] == "changes_requested"
        assert data["thesis"]["status"] == THESIS_STATUS_CHANGES_REQUESTED
        assert data["version"]["stage"] == "revision"

    def test_review_not_in_mentor_review_stage(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user, status=THESIS_STATUS_ANALYSIS_DONE)
        response = client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "approved"},
        )
        assert response.status_code == 400

    def test_review_invalid_decision(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user)
        response = client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "rejected"},
        )
        assert response.status_code == 422

    def test_review_creates_notification(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user)
        client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "approved", "comments": "Well done."},
        )
        db = SessionLocal()
        notifications = db.query(Notification).filter(Notification.user_id == student_user.id).all()
        db.close()
        assert len(notifications) == 1
        assert "导师评审结果" in notifications[0].title

    def test_review_removed_from_pending(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user)
        client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "approved"},
        )
        response = client.get("/mentor/pending-reviews", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        assert response.json() == []

    def test_review_requires_binding(self, mentor_token, student_user):
        """Mentor cannot review a thesis from a student not bound to them."""
        version_id = _create_ready_version(student_user)
        response = client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "approved"},
        )
        assert response.status_code == 403


class TestMentorReviewsList:
    def test_list_reviews_for_version(self, mentor_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        version_id = _create_ready_version(student_user)
        client.post(
            "/mentor/reviews",
            headers=_auth_headers(mentor_token),
            json={"version_id": version_id, "decision": "approved"},
        )
        response = client.get(f"/mentor/reviews/{version_id}", headers=_auth_headers(mentor_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["decision"] == "approved"

    def test_list_reviews_version_not_found(self, mentor_token):
        response = client.get("/mentor/reviews/99999", headers=_auth_headers(mentor_token))
        assert response.status_code == 404


class TestMentorAccessControl:
    def test_admin_can_access_pending_reviews(self, admin_token, mentor_user, student_user):
        _bind_mentor_student(mentor_user.id, student_user.id)
        _create_ready_version(student_user)
        response = client.get("/mentor/pending-reviews", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_unauthenticated_cannot_access(self):
        response = client.get("/mentor/pending-reviews")
        assert response.status_code == 401


class TestSubmitForMentor:
    def test_submit_for_mentor_updates_status(self, student_token, student_user):
        version_id = _create_ready_version(student_user, status=THESIS_STATUS_ANALYSIS_DONE, ready=False)
        db = SessionLocal()
        task = db.query(AnalysisTask).filter(AnalysisTask.version_id == version_id).first()
        db.close()

        response = client.post(
            f"/tasks/{task.id}/submit-for-mentor",
            headers=_auth_headers(student_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["student_ready_for_mentor"] is True

        db = SessionLocal()
        thesis = db.query(Thesis).join(Thesis.versions).filter(ThesisVersion.id == version_id).first()
        db.close()
        assert thesis.status == THESIS_STATUS_MENTOR_REVIEW

    def test_submit_for_mentor_not_completed_fails(self, student_token, student_user):
        db = SessionLocal()
        thesis = Thesis(student_id=student_user.id, title="Test", status=THESIS_STATUS_ANALYSIS_DONE)
        db.add(thesis)
        db.flush()
        version = ThesisVersion(thesis_id=thesis.id, version_no=1, stage="draft", file_path="/tmp/test.pdf")
        db.add(version)
        db.flush()
        task = AnalysisTask(version_id=version.id, status="running", student_ready_for_mentor=False)
        db.add(task)
        db.commit()
        task_id = task.id
        db.close()

        response = client.post(
            f"/tasks/{task_id}/submit-for-mentor",
            headers=_auth_headers(student_token),
        )
        assert response.status_code == 400
