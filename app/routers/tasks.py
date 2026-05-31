from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.core.constants import ROLE_ACADEMIC, ROLE_ADMIN, ROLE_MENTOR, ROLE_STUDENT
from app.db import get_db
from app.deps import require_roles
from app.models import AnalysisTask, ThesisVersion
from app.schemas.analysis import AnalysisResult
from app.schemas.thesis import AnalysisTaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _parse_result(task: AnalysisTask) -> tuple[AnalysisResult | None, str | None]:
    if not isinstance(task.result_json, dict):
        if task.result_json is None:
            return None, task.error_message
        return None, task.error_message or "分析结果暂时不可用，请稍后刷新。"

    try:
        return AnalysisResult.model_validate(task.result_json), task.error_message
    except ValidationError:
        return None, task.error_message or "分析结果暂时不可用，请稍后刷新。"


def _build_task_read(task: AnalysisTask) -> AnalysisTaskRead:
    result, error_message = _parse_result(task)
    version = task.version
    thesis = version.thesis if version else None
    return AnalysisTaskRead(
        id=task.id,
        thesis_id=thesis.id if thesis else None,
        version_id=version.id if version else None,
        thesis_title=thesis.title if thesis else None,
        status=task.status,
        result=result,
        error_message=error_message,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


@router.get("", response_model=list[AnalysisTaskRead])
def list_tasks(
    current_user=Depends(require_roles(ROLE_STUDENT, ROLE_ADMIN, ROLE_MENTOR, ROLE_ACADEMIC)),
    db: Session = Depends(get_db),
) -> list[AnalysisTaskRead]:
    query = (
        db.query(AnalysisTask)
        .options(joinedload(AnalysisTask.version).joinedload(ThesisVersion.thesis))
        .order_by(AnalysisTask.created_at.desc())
    )

    if current_user.role == ROLE_STUDENT:
        query = query.join(AnalysisTask.version).join(ThesisVersion.thesis).filter_by(student_id=current_user.id)

    tasks = query.all()
    return [_build_task_read(task) for task in tasks]


@router.get("/{task_id}", response_model=AnalysisTaskRead)
def get_task(
    task_id: int,
    current_user=Depends(require_roles(ROLE_STUDENT, ROLE_ADMIN, ROLE_MENTOR, ROLE_ACADEMIC)),
    db: Session = Depends(get_db),
) -> AnalysisTaskRead:
    task = db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if current_user.role == ROLE_STUDENT:
        thesis = task.version.thesis if task.version else None
        if not thesis or thesis.student_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    return _build_task_read(task)
