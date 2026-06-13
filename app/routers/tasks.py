from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.constants import (
    ROLE_ACADEMIC,
    ROLE_ADMIN,
    ROLE_MENTOR,
    ROLE_STUDENT,
    THESIS_STATUS_MENTOR_REVIEW,
)
from app.db import get_db
from app.deps import require_roles
from app.models import AnalysisTask, ThesisVersion
from app.schemas.analysis import AnalysisLLMUsageSummary, AnalysisResult
from app.schemas.thesis import AnalysisTaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _is_dev() -> bool:
    return settings.is_dev()


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
    llm_usage_summary = None
    if isinstance(task.llm_usage_summary_json, dict):
        llm_usage_summary = AnalysisLLMUsageSummary.model_validate(task.llm_usage_summary_json)
    return AnalysisTaskRead(
        id=task.id,
        thesis_id=thesis.id if thesis else None,
        version_id=version.id if version else None,
        thesis_title=thesis.title if thesis else None,
        status=task.status,
        result=result,
        llm_usage_summary=llm_usage_summary,
        error_message=error_message,
        student_ready_for_mentor=task.student_ready_for_mentor,
        ignored_issue_keys=task.ignored_issue_keys_json,
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


@router.post("/{task_id}/submit-for-mentor", response_model=AnalysisTaskRead)
def submit_for_mentor(
    task_id: int,
    current_user=Depends(require_roles(ROLE_STUDENT)),
    db: Session = Depends(get_db),
) -> AnalysisTaskRead:
    task = db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    thesis = task.version.thesis if task.version else None
    if not thesis or thesis.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="分析尚未完成，无法提交导师评审。")

    if thesis.status == THESIS_STATUS_MENTOR_REVIEW and task.student_ready_for_mentor:
        raise HTTPException(status_code=400, detail="当前论文已在导师审核中，请等待导师处理。")

    result, _ = _parse_result(task)
    if result and not _is_dev():
        ignored_keys = set(task.ignored_issue_keys_json or [])
        for idx, issue in enumerate(result.issues):
            key = f"{issue.page}-{issue.issue_type}-{idx}"
            if key in ignored_keys:
                continue
            severity = issue.severity.lower()
            is_high_medium = severity not in ("低", "low", "minor", "info")
            if is_high_medium:
                raise HTTPException(
                    status_code=400,
                    detail=f"存在未处理的中高等级问题：{issue.issue_type}，请先处理或切换到开发环境进行调试。",
                )

    task.student_ready_for_mentor = True
    if thesis:
        thesis.status = THESIS_STATUS_MENTOR_REVIEW
    db.commit()
    db.refresh(task)
    return _build_task_read(task)


@router.post("/{task_id}/issues/{issue_key}/ignore", response_model=AnalysisTaskRead)
def ignore_issue(
    task_id: int,
    issue_key: str,
    current_user=Depends(require_roles(ROLE_STUDENT)),
    db: Session = Depends(get_db),
) -> AnalysisTaskRead:
    task = db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    thesis = task.version.thesis if task.version else None
    if not thesis or thesis.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    result, error_message = _parse_result(task)
    if not result:
        raise HTTPException(status_code=400, detail="分析结果暂时不可用。")

    # find the issue by key
    issue = None
    for idx, item in enumerate(result.issues):
        key = f"{item.page}-{item.issue_type}-{idx}"
        if key == issue_key:
            issue = item
            break
    if not issue:
        raise HTTPException(status_code=404, detail="问题未找到。")

    # in production, reject medium/high severity ignores
    severity = issue.severity.lower()
    is_high_medium = severity not in ("低", "low", "minor", "info")
    if is_high_medium and not _is_dev():
        raise HTTPException(
            status_code=400,
            detail="生产环境下不允许忽略中高等级问题。",
        )

    # persist
    ignored_keys = set(task.ignored_issue_keys_json or [])
    ignored_keys.add(issue_key)
    task.ignored_issue_keys_json = sorted(ignored_keys)
    db.commit()
    db.refresh(task)
    return _build_task_read(task)
