from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ANALYSIS_STATUS_PENDING,
    ROLE_STUDENT,
    THESIS_STATUS_ANALYSIS_PENDING,
    VERSION_STAGE_DRAFT,
)
from app.db import get_db
from app.deps import require_roles
from app.models import AnalysisTask, Thesis, ThesisVersion
from app.schemas.thesis import AnalysisTaskRead, DraftSubmissionResponse
from app.services.analysis import run_analysis_task
from app.services.file_uploads import remove_uploaded_file, save_pdf, validate_pdf_content

router = APIRouter(prefix="/theses", tags=["theses"])


@router.post("/drafts", response_model=DraftSubmissionResponse)
def submit_draft(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_roles(ROLE_STUDENT)),
    db: Session = Depends(get_db),
) -> DraftSubmissionResponse:
    file_path = save_pdf(file, current_user.id)
    pdf_path = settings.base_dir / file_path
    try:
        validate_pdf_content(pdf_path)
    except Exception:
        remove_uploaded_file(pdf_path)
        raise

    thesis = Thesis(
        student_id=current_user.id,
        title=title,
        status=THESIS_STATUS_ANALYSIS_PENDING,
    )
    db.add(thesis)
    db.flush()

    version = ThesisVersion(
        thesis_id=thesis.id,
        version_no=1,
        stage=VERSION_STAGE_DRAFT,
        file_path=file_path,
    )
    db.add(version)
    db.flush()

    task = AnalysisTask(
        version_id=version.id,
        status=ANALYSIS_STATUS_PENDING,
    )
    db.add(task)
    db.commit()

    background_tasks.add_task(run_analysis_task, task.id)

    task_read = AnalysisTaskRead(
        id=task.id,
        status=task.status,
        result=None,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )

    return DraftSubmissionResponse(
        thesis_id=thesis.id,
        version_id=version.id,
        task=task_read,
    )
