from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ACADEMIC, ROLE_ADMIN, ROLE_MENTOR, ROLE_STUDENT
from app.db import get_db
from app.deps import require_roles
from app.models import AnalysisTask
from app.schemas.analysis import AnalysisResult
from app.schemas.thesis import AnalysisTaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


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

    result = AnalysisResult.model_validate(task.result_json) if task.result_json else None
    return AnalysisTaskRead(
        id=task.id,
        status=task.status,
        result=result,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )
