from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, joinedload

from app.core.constants import ROLE_ADMIN
from app.db import get_db
from app.deps import require_roles
from app.models import AnalysisTask, Thesis, ThesisVersion, User
from app.schemas.thesis import AnalysisTaskRead

router = APIRouter(prefix="/admin", tags=["admin"])

require_admin = require_roles(ROLE_ADMIN)


class UserAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    is_active: bool
    created_at: str | None = None


class UserListResponse(BaseModel):
    total: int
    items: list[UserAdminRead]


class TaskAdminRead(AnalysisTaskRead):
    pass


class TaskListResponse(BaseModel):
    total: int
    items: list[TaskAdminRead]


class TaskStatusUpdate(BaseModel):
    status: str
    error_message: str | None = None


class ThesisAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    title: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class ThesisListResponse(BaseModel):
    total: int
    items: list[ThesisAdminRead]


class VersionAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thesis_id: int
    version_no: int
    stage: str
    file_path: str
    submitted_at: str | None = None


class MessageResponse(BaseModel):
    message: str


def _to_user_read(user: User) -> UserAdminRead:
    return UserAdminRead(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=str(user.created_at) if user.created_at else None,
    )


def _to_thesis_read(thesis: Thesis) -> ThesisAdminRead:
    return ThesisAdminRead(
        id=thesis.id,
        student_id=thesis.student_id,
        title=thesis.title,
        status=thesis.status,
        created_at=str(thesis.created_at) if thesis.created_at else None,
        updated_at=str(thesis.updated_at) if thesis.updated_at else None,
    )


@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 100,
    role: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> UserListResponse:
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return UserListResponse(total=total, items=[_to_user_read(u) for u in items])


@router.get("/users/{user_id}", response_model=UserAdminRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> UserAdminRead:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _to_user_read(user)


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> MessageResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role == ROLE_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot delete admin user via API.")
    db.delete(user)
    db.commit()
    return MessageResponse(message="User deleted.")


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    user_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> TaskListResponse:
    from app.routers.tasks import _build_task_read

    query = (
        db.query(AnalysisTask)
        .options(joinedload(AnalysisTask.version).joinedload(ThesisVersion.thesis))
        .order_by(AnalysisTask.created_at.desc())
    )
    if status:
        query = query.filter(AnalysisTask.status == status)
    if user_id is not None:
        query = query.join(AnalysisTask.version).join(ThesisVersion.thesis).filter(Thesis.student_id == user_id)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return TaskListResponse(total=total, items=[_build_task_read(t) for t in items])


@router.get("/tasks/{task_id}", response_model=TaskAdminRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> TaskAdminRead:
    from app.routers.tasks import _build_task_read

    task = db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return _build_task_read(task)


@router.patch("/tasks/{task_id}/status", response_model=TaskAdminRead)
def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> TaskAdminRead:
    from app.routers.tasks import _build_task_read

    task = db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    task.status = payload.status
    if payload.error_message is not None:
        task.error_message = payload.error_message
    db.commit()
    db.refresh(task)
    return _build_task_read(task)


@router.delete("/tasks/{task_id}", response_model=MessageResponse)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> MessageResponse:
    task = db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    db.delete(task)
    db.commit()
    return MessageResponse(message="Task deleted.")


@router.get("/theses", response_model=ThesisListResponse)
def list_theses(
    skip: int = 0,
    limit: int = 100,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> ThesisListResponse:
    query = db.query(Thesis)
    if student_id is not None:
        query = query.filter(Thesis.student_id == student_id)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return ThesisListResponse(total=total, items=[_to_thesis_read(t) for t in items])


@router.get("/theses/{thesis_id}", response_model=ThesisAdminRead)
def get_thesis(
    thesis_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> ThesisAdminRead:
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found.")
    return _to_thesis_read(thesis)


@router.delete("/theses/{thesis_id}", response_model=MessageResponse)
def delete_thesis(
    thesis_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> MessageResponse:
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found.")
    db.delete(thesis)
    db.commit()
    return MessageResponse(message="Thesis and its versions deleted.")


@router.get("/theses/{thesis_id}/versions", response_model=list[VersionAdminRead])
def list_thesis_versions(
    thesis_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[VersionAdminRead]:
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found.")
    versions = (
        db.query(ThesisVersion)
        .filter(ThesisVersion.thesis_id == thesis_id)
        .order_by(ThesisVersion.version_no.desc())
        .all()
    )
    return [
        VersionAdminRead(
            id=v.id,
            thesis_id=v.thesis_id,
            version_no=v.version_no,
            stage=v.stage,
            file_path=v.file_path,
            submitted_at=str(v.submitted_at) if v.submitted_at else None,
        )
        for v in versions
    ]
