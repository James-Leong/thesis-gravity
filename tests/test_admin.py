import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db import SessionLocal, init_db
from app.main import app
from app.models import AnalysisTask, Thesis, ThesisVersion, User

client = TestClient(app)


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    db = SessionLocal()
    db.query(AnalysisTask).delete()
    db.query(ThesisVersion).delete()
    db.query(Thesis).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


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
def student_user():
    db = SessionLocal()
    user = User(email="student@example.com", password_hash=hash_password("secret"), role="student")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(str(admin_user.id))


@pytest.fixture
def student_token(student_user):
    return create_access_token(str(student_user.id))


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestAdminUsers:
    def test_list_users_as_admin(self, admin_token):
        response = client.get("/admin/users", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data

    def test_list_users_as_student_forbidden(self, student_token):
        response = client.get("/admin/users", headers=_auth_headers(student_token))
        assert response.status_code == 403

    def test_get_user(self, admin_token, student_user):
        response = client.get(f"/admin/users/{student_user.id}", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        assert response.json()["email"] == "student@example.com"

    def test_delete_user(self, admin_token, student_user):
        response = client.delete(f"/admin/users/{student_user.id}", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        response = client.get(f"/admin/users/{student_user.id}", headers=_auth_headers(admin_token))
        assert response.status_code == 404


class TestAdminTasks:
    def test_list_tasks(self, admin_token, student_user):
        db = SessionLocal()
        thesis = Thesis(student_id=student_user.id, title="Test", status="draft_submitted")
        db.add(thesis)
        db.flush()
        version = ThesisVersion(thesis_id=thesis.id, version_no=1, stage="draft", file_path="/tmp/test.pdf")
        db.add(version)
        db.flush()
        task = AnalysisTask(version_id=version.id, status="running")
        db.add(task)
        db.commit()
        db.close()

        response = client.get("/admin/tasks", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_update_task_status(self, admin_token, student_user):
        db = SessionLocal()
        thesis = Thesis(student_id=student_user.id, title="Test", status="draft_submitted")
        db.add(thesis)
        db.flush()
        version = ThesisVersion(thesis_id=thesis.id, version_no=1, stage="draft", file_path="/tmp/test.pdf")
        db.add(version)
        db.flush()
        task = AnalysisTask(version_id=version.id, status="running")
        db.add(task)
        db.commit()
        task_id = task.id
        db.close()

        response = client.patch(
            f"/admin/tasks/{task_id}/status",
            json={"status": "failed", "error_message": "Force reset by admin."},
            headers=_auth_headers(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert response.json()["error_message"] == "Force reset by admin."

    def test_delete_task(self, admin_token, student_user):
        db = SessionLocal()
        thesis = Thesis(student_id=student_user.id, title="Test", status="draft_submitted")
        db.add(thesis)
        db.flush()
        version = ThesisVersion(thesis_id=thesis.id, version_no=1, stage="draft", file_path="/tmp/test.pdf")
        db.add(version)
        db.flush()
        task = AnalysisTask(version_id=version.id, status="pending")
        db.add(task)
        db.commit()
        task_id = task.id
        db.close()

        response = client.delete(f"/admin/tasks/{task_id}", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        response = client.get(f"/admin/tasks/{task_id}", headers=_auth_headers(admin_token))
        assert response.status_code == 404


class TestAdminTheses:
    def test_list_theses(self, admin_token, student_user):
        db = SessionLocal()
        thesis = Thesis(student_id=student_user.id, title="Test", status="draft_submitted")
        db.add(thesis)
        db.commit()
        db.close()

        response = client.get("/admin/theses", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_delete_thesis(self, admin_token, student_user):
        db = SessionLocal()
        thesis = Thesis(student_id=student_user.id, title="Test", status="draft_submitted")
        db.add(thesis)
        db.commit()
        thesis_id = thesis.id
        db.close()

        response = client.delete(f"/admin/theses/{thesis_id}", headers=_auth_headers(admin_token))
        assert response.status_code == 200
        response = client.get(f"/admin/theses/{thesis_id}", headers=_auth_headers(admin_token))
        assert response.status_code == 404
