from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.constants import (
    ANALYSIS_STATUS_PENDING,
    ANALYSIS_STATUS_RUNNING,
    MENTOR_RELATION_STATUS_APPROVED,
    ROLE_ACADEMIC,
    ROLE_ADMIN,
    ROLE_MENTOR,
    ROLE_STUDENT,
    THESIS_STATUS_ANALYSIS_PENDING,
    THESIS_STATUS_APPROVED,
    THESIS_STATUS_CHANGES_REQUESTED,
    THESIS_STATUS_MENTOR_REVIEW,
    VERSION_STAGE_DRAFT,
    VERSION_STAGE_REVISION,
)
from app.db import get_db
from app.deps import require_roles
from app.models import AnalysisTask, MentorRelation, Thesis, ThesisVersion
from app.routers.tasks import _build_task_read
from app.schemas.thesis import (
    AnalysisTaskRead,
    DraftSubmissionResponse,
    ThesisVersionTaskRead,
    ThesisWorkspaceRead,
)
from app.services.analysis import run_analysis_task
from app.services.file_uploads import remove_uploaded_file, save_pdf, validate_pdf_content

router = APIRouter(prefix="/theses", tags=["theses"])


def _get_latest_task(version: ThesisVersion) -> AnalysisTask | None:
    if not version.analysis_tasks:
        return None
    return max(version.analysis_tasks, key=lambda task: task.created_at)


def _get_latest_version(thesis: Thesis) -> ThesisVersion | None:
    if not thesis.versions:
        return None
    return max(thesis.versions, key=lambda version: version.version_no)


def _build_version_read(version: ThesisVersion) -> ThesisVersionTaskRead:
    latest_task = _get_latest_task(version)
    return ThesisVersionTaskRead(
        id=version.id,
        version_no=version.version_no,
        stage=version.stage,
        file_path=version.file_path,
        submitted_at=version.submitted_at,
        latest_task=_build_task_read(latest_task) if latest_task else None,
    )


def _build_thesis_workspace_read(thesis: Thesis) -> ThesisWorkspaceRead:
    versions = sorted(thesis.versions, key=lambda version: version.version_no, reverse=True)
    current_version = versions[0] if versions else None
    return ThesisWorkspaceRead(
        id=thesis.id,
        title=thesis.title,
        status=thesis.status,
        created_at=thesis.created_at,
        updated_at=thesis.updated_at,
        current_version=_build_version_read(current_version) if current_version else None,
        versions=[_build_version_read(version) for version in versions],
    )


@router.get("", response_model=list[ThesisWorkspaceRead])
def list_theses(
    current_user=Depends(require_roles(ROLE_STUDENT)),
    db: Session = Depends(get_db),
) -> list[ThesisWorkspaceRead]:
    theses = (
        db.query(Thesis)
        .options(joinedload(Thesis.versions).joinedload(ThesisVersion.analysis_tasks))
        .filter(Thesis.student_id == current_user.id)
        .order_by(Thesis.updated_at.desc())
        .all()
    )
    return [_build_thesis_workspace_read(thesis) for thesis in theses]


@router.post("/drafts", response_model=DraftSubmissionResponse)
def submit_draft(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    thesis_id: int | None = Form(None),
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

    try:
        thesis: Thesis | None = None
        next_version_no = 1
        version_stage = VERSION_STAGE_DRAFT

        if thesis_id is not None:
            thesis = (
                db.query(Thesis)
                .options(joinedload(Thesis.versions).joinedload(ThesisVersion.analysis_tasks))
                .filter(Thesis.id == thesis_id, Thesis.student_id == current_user.id)
                .first()
            )
            if not thesis:
                raise HTTPException(status_code=404, detail="论文任务不存在。")
            if thesis.status == THESIS_STATUS_MENTOR_REVIEW:
                raise HTTPException(status_code=400, detail="论文正在导师审核中，暂不允许再次提交。")
            if thesis.status == THESIS_STATUS_APPROVED:
                raise HTTPException(status_code=400, detail="论文任务已完成，如需继续修改请联系导师或管理员。")

            latest_version = _get_latest_version(thesis)
            latest_task = _get_latest_task(latest_version) if latest_version else None
            if latest_task and latest_task.status in {ANALYSIS_STATUS_PENDING, ANALYSIS_STATUS_RUNNING}:
                raise HTTPException(status_code=400, detail="当前论文仍有 AI 分析任务进行中，请等待完成后再提交。")

            previous_status = thesis.status
            thesis.title = title
            thesis.status = THESIS_STATUS_ANALYSIS_PENDING
            next_version_no = (latest_version.version_no + 1) if latest_version else 1
            version_stage = (
                VERSION_STAGE_REVISION
                if previous_status == THESIS_STATUS_CHANGES_REQUESTED or next_version_no > 1
                else VERSION_STAGE_DRAFT
            )
        else:
            thesis = Thesis(
                student_id=current_user.id,
                title=title,
                status=THESIS_STATUS_ANALYSIS_PENDING,
            )
            db.add(thesis)
            db.flush()

        version = ThesisVersion(
            thesis_id=thesis.id,
            version_no=next_version_no,
            stage=version_stage,
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
    except Exception:
        remove_uploaded_file(pdf_path)
        raise

    background_tasks.add_task(run_analysis_task, task.id)

    task_read = AnalysisTaskRead(
        id=task.id,
        thesis_id=thesis.id,
        version_id=version.id,
        thesis_title=thesis.title,
        status=task.status,
        result=None,
        llm_usage_summary=None,
        error_message=task.error_message,
        student_ready_for_mentor=task.student_ready_for_mentor,
        ignored_issue_keys=task.ignored_issue_keys_json,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )

    return DraftSubmissionResponse(
        thesis_id=thesis.id,
        version_id=version.id,
        task=task_read,
    )


@router.get("/versions/{version_id}/file")
def get_version_file(
    version_id: int,
    current_user=Depends(require_roles(ROLE_STUDENT, ROLE_MENTOR, ROLE_ADMIN, ROLE_ACADEMIC)),
    db: Session = Depends(get_db),
):
    version = db.get(ThesisVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found.")

    thesis = version.thesis
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found.")

    if current_user.role == ROLE_STUDENT and thesis.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    if current_user.role == ROLE_MENTOR:
        relation = (
            db.query(MentorRelation)
            .filter(
                MentorRelation.mentor_id == current_user.id,
                MentorRelation.student_id == thesis.student_id,
                MentorRelation.status == MENTOR_RELATION_STATUS_APPROVED,
            )
            .first()
        )
        if not relation:
            raise HTTPException(status_code=403, detail="只能查看已绑定学生的论文。")

    absolute_path = (settings.base_dir / version.file_path).resolve()
    base_dir = settings.base_dir.resolve()
    if not absolute_path.is_file() or base_dir not in absolute_path.parents:
        raise HTTPException(status_code=404, detail="论文文件不存在。")

    filename = Path(version.file_path).name
    return FileResponse(
        absolute_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
