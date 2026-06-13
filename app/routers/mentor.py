from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.constants import (
    MENTOR_RELATION_STATUS_APPROVED,
    MENTOR_RELATION_STATUS_PENDING,
    MENTOR_RELATION_STATUS_REJECTED,
    ROLE_ACADEMIC,
    ROLE_ADMIN,
    ROLE_MENTOR,
    ROLE_STUDENT,
    THESIS_STATUS_APPROVED,
    THESIS_STATUS_CHANGES_REQUESTED,
    THESIS_STATUS_MENTOR_REVIEW,
    VERSION_STAGE_FINAL,
    VERSION_STAGE_REVISION,
)
from app.db import get_db
from app.deps import require_roles
from app.models import AnalysisTask, MentorRelation, MentorReview, Notification, Thesis, ThesisVersion, User
from app.routers.tasks import _build_task_read
from app.schemas.mentor import (
    MentorApplicationRead,
    MentorListRead,
    MentorPendingReviewRead,
    MentorRelationCreate,
    MentorRelationRead,
    MentorReviewCreate,
    MentorReviewRead,
    MentorReviewSubmissionRead,
    MentorStudentListRead,
    MentorStudentRead,
    MentorThesisRead,
    MentorTrackedThesisRead,
    MentorUserRead,
    MentorVersionDetailRead,
    MentorVersionRead,
    StudentApplicationRead,
)

router = APIRouter(prefix="/mentor", tags=["mentor"])

require_mentor_scope = require_roles(ROLE_MENTOR, ROLE_ADMIN, ROLE_ACADEMIC)


def _to_user_read(user: User) -> MentorUserRead:
    return MentorUserRead(id=user.id, email=user.email, name=user.name)


def _to_thesis_read(thesis: Thesis) -> MentorThesisRead:
    return MentorThesisRead(
        id=thesis.id,
        title=thesis.title,
        status=thesis.status,
        student=_to_user_read(thesis.student),
    )


def _to_version_read(version: ThesisVersion) -> MentorVersionRead:
    return MentorVersionRead(
        id=version.id,
        version_no=version.version_no,
        stage=version.stage,
        file_path=version.file_path,
        submitted_at=version.submitted_at,
    )


def _get_latest_task(db: Session, version_id: int) -> AnalysisTask | None:
    return (
        db.query(AnalysisTask)
        .filter(AnalysisTask.version_id == version_id)
        .order_by(AnalysisTask.created_at.desc())
        .first()
    )


def _get_latest_version(thesis: Thesis) -> ThesisVersion | None:
    if not thesis.versions:
        return None
    return max(thesis.versions, key=lambda version: version.version_no)


def _get_latest_review(db: Session, version_id: int) -> MentorReview | None:
    return (
        db.query(MentorReview)
        .filter(MentorReview.version_id == version_id)
        .order_by(MentorReview.created_at.desc())
        .first()
    )


def _get_bound_student_ids(db: Session, mentor_id: int) -> list[int]:
    """Return the set of student IDs bound to a mentor via an approved relation."""
    rows = (
        db.query(MentorRelation.student_id)
        .filter(
            MentorRelation.mentor_id == mentor_id,
            MentorRelation.status == MENTOR_RELATION_STATUS_APPROVED,
        )
        .all()
    )
    return [row[0] for row in rows]


# ── Student endpoints ──────────────────────────────────────────


@router.get("/list", response_model=list[MentorListRead])
def list_mentors(
    q: str = "",
    current_user=Depends(require_roles(ROLE_STUDENT)),
    db: Session = Depends(get_db),
) -> list[MentorListRead]:
    query = db.query(User).filter(User.role == ROLE_MENTOR, User.is_active.is_(True))
    if q.strip():
        search = f"%{q.strip()}%"
        query = query.filter((User.email.ilike(search)) | (User.name.ilike(search)))
    mentors = query.order_by(User.email).all()
    return [MentorListRead(id=m.id, email=m.email, name=m.name) for m in mentors]


@router.post("/applications", response_model=MentorRelationRead)
def create_application(
    payload: MentorRelationCreate,
    current_user=Depends(require_roles(ROLE_STUDENT)),
    db: Session = Depends(get_db),
) -> MentorRelationRead:
    mentor = db.query(User).filter(User.id == payload.mentor_id, User.role == ROLE_MENTOR).first()
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor not found.")

    existing = db.query(MentorRelation).filter(MentorRelation.student_id == current_user.id).first()
    if existing:
        if existing.status == MENTOR_RELATION_STATUS_APPROVED:
            raise HTTPException(status_code=400, detail="你已有绑定的导师，无法再次申请。")
        if existing.status == MENTOR_RELATION_STATUS_PENDING:
            raise HTTPException(status_code=400, detail="你已有待审批的申请，请等待导师处理。")
        # If previously rejected, allow re-application — update the existing row
        existing.mentor_id = payload.mentor_id
        existing.status = MENTOR_RELATION_STATUS_PENDING
        db.commit()
        db.refresh(existing)
        return existing

    rel = MentorRelation(mentor_id=payload.mentor_id, student_id=current_user.id)
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/my-application", response_model=StudentApplicationRead)
def my_application(
    current_user=Depends(require_roles(ROLE_STUDENT)),
    db: Session = Depends(get_db),
) -> StudentApplicationRead:
    rel = db.query(MentorRelation).filter(MentorRelation.student_id == current_user.id).first()
    if not rel:
        return StudentApplicationRead(has_application=False)
    mentor = db.get(User, rel.mentor_id)
    return StudentApplicationRead(
        has_application=True,
        application=MentorRelationRead.model_validate(rel),
        mentor=MentorListRead(id=mentor.id, email=mentor.email, name=mentor.name) if mentor else None,
    )


# ── Mentor endpoints ───────────────────────────────────────────


@router.get("/applications", response_model=list[MentorApplicationRead])
def list_applications(
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> list[MentorApplicationRead]:
    rels = (
        db.query(MentorRelation)
        .filter(
            MentorRelation.mentor_id == current_user.id,
            MentorRelation.status == MENTOR_RELATION_STATUS_PENDING,
        )
        .order_by(MentorRelation.created_at.desc())
        .all()
    )
    result: list[MentorApplicationRead] = []
    for rel in rels:
        student = db.get(User, rel.student_id)
        if student:
            result.append(
                MentorApplicationRead(
                    application=MentorRelationRead.model_validate(rel),
                    student=MentorListRead(id=student.id, email=student.email, name=student.name),
                )
            )
    return result


@router.post("/applications/{application_id}/approve", response_model=MentorRelationRead)
def approve_application(
    application_id: int,
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> MentorRelationRead:
    rel = db.get(MentorRelation, application_id)
    if not rel or rel.mentor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found.")
    if rel.status != MENTOR_RELATION_STATUS_PENDING:
        raise HTTPException(status_code=400, detail="申请已处理。")

    # Ensure student isn't already approved with another mentor
    existing_approved = (
        db.query(MentorRelation)
        .filter(
            MentorRelation.student_id == rel.student_id,
            MentorRelation.status == MENTOR_RELATION_STATUS_APPROVED,
            MentorRelation.id != rel.id,
        )
        .first()
    )
    if existing_approved:
        raise HTTPException(status_code=400, detail="该学生已绑定其他导师。")

    rel.status = MENTOR_RELATION_STATUS_APPROVED
    db.commit()
    db.refresh(rel)
    return rel


@router.post("/applications/{application_id}/reject", response_model=MentorRelationRead)
def reject_application(
    application_id: int,
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> MentorRelationRead:
    rel = db.get(MentorRelation, application_id)
    if not rel or rel.mentor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found.")
    if rel.status != MENTOR_RELATION_STATUS_PENDING:
        raise HTTPException(status_code=400, detail="申请已处理。")

    rel.status = MENTOR_RELATION_STATUS_REJECTED
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/students", response_model=MentorStudentListRead)
def list_students(
    skip: int = 0,
    limit: int = 20,
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> MentorStudentListRead:
    base = db.query(MentorRelation).filter(
        MentorRelation.mentor_id == current_user.id,
        MentorRelation.status == MENTOR_RELATION_STATUS_APPROVED,
    )
    total = base.count()
    rels = base.order_by(MentorRelation.updated_at.desc()).offset(skip).limit(limit).all()

    items: list[MentorStudentRead] = []
    for rel in rels:
        student = db.get(User, rel.student_id)
        if not student:
            continue
        thesis_count = db.query(Thesis).filter(Thesis.student_id == student.id).count()
        items.append(
            MentorStudentRead(
                id=student.id,
                email=student.email,
                name=student.name,
                thesis_count=thesis_count,
                bound_at=rel.updated_at,
            )
        )
    return MentorStudentListRead(total=total, items=items)


# ── Review endpoints ───────────────────────────────────────────


@router.get("/pending-reviews", response_model=list[MentorPendingReviewRead])
def list_pending_reviews(
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> list[MentorPendingReviewRead]:
    # Only show theses from students bound to this mentor
    # Admins and academics see all pending reviews
    if current_user.role in (ROLE_ADMIN, ROLE_ACADEMIC):
        versions = (
            db.query(ThesisVersion)
            .join(ThesisVersion.thesis)
            .join(ThesisVersion.analysis_tasks)
            .filter(
                Thesis.status == THESIS_STATUS_MENTOR_REVIEW,
                AnalysisTask.student_ready_for_mentor.is_(True),
            )
            .order_by(ThesisVersion.submitted_at.desc())
            .options(joinedload(ThesisVersion.thesis).joinedload(Thesis.student))
            .all()
        )
    else:
        bound_student_ids = _get_bound_student_ids(db, current_user.id)
        if not bound_student_ids:
            return []
        versions = (
            db.query(ThesisVersion)
            .join(ThesisVersion.thesis)
            .join(ThesisVersion.analysis_tasks)
            .filter(
                Thesis.status == THESIS_STATUS_MENTOR_REVIEW,
                Thesis.student_id.in_(bound_student_ids),
                AnalysisTask.student_ready_for_mentor.is_(True),
            )
            .order_by(ThesisVersion.submitted_at.desc())
            .options(joinedload(ThesisVersion.thesis).joinedload(Thesis.student))
            .all()
        )

    result: list[MentorPendingReviewRead] = []
    for version in versions:
        latest_version = _get_latest_version(version.thesis)
        if not latest_version or latest_version.id != version.id:
            continue
        task = _get_latest_task(db, version.id)
        if not task or not task.student_ready_for_mentor:
            continue
        result.append(
            MentorPendingReviewRead(
                version=_to_version_read(version),
                thesis=_to_thesis_read(version.thesis),
                latest_task=_build_task_read(task),
            )
        )
    return result


@router.get("/theses", response_model=list[MentorTrackedThesisRead])
def list_tracked_theses(
    q: str = "",
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> list[MentorTrackedThesisRead]:
    query = db.query(Thesis).options(
        joinedload(Thesis.student),
        joinedload(Thesis.versions).joinedload(ThesisVersion.analysis_tasks),
    )

    if current_user.role == ROLE_MENTOR:
        bound_student_ids = _get_bound_student_ids(db, current_user.id)
        if not bound_student_ids:
            return []
        query = query.filter(Thesis.student_id.in_(bound_student_ids))

    if q.strip():
        search = f"%{q.strip()}%"
        query = query.join(Thesis.student).filter(
            (Thesis.title.ilike(search)) | (User.email.ilike(search)) | (User.name.ilike(search))
        )

    theses = query.order_by(Thesis.updated_at.desc()).all()

    result: list[MentorTrackedThesisRead] = []
    for thesis in theses:
        latest_version = _get_latest_version(thesis)
        if not latest_version:
            continue
        latest_task = _get_latest_task(db, latest_version.id)
        latest_review = _get_latest_review(db, latest_version.id)
        result.append(
            MentorTrackedThesisRead(
                thesis=_to_thesis_read(thesis),
                current_version=_to_version_read(latest_version),
                latest_task=_build_task_read(latest_task) if latest_task else None,  # type: ignore[arg-type]
                latest_review=MentorReviewRead.model_validate(latest_review) if latest_review else None,
            )
        )
    return result


@router.get("/versions/{version_id}", response_model=MentorVersionDetailRead)
def get_version_detail(
    version_id: int,
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> MentorVersionDetailRead:
    version = db.get(ThesisVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found.")
    thesis = version.thesis
    if current_user.role == ROLE_MENTOR:
        bound_student_ids = _get_bound_student_ids(db, current_user.id)
        if not thesis or thesis.student_id not in bound_student_ids:
            raise HTTPException(status_code=403, detail="只能查看绑定学生的论文。")

    task = _get_latest_task(db, version.id)
    reviews = (
        db.query(MentorReview)
        .filter(MentorReview.version_id == version_id)
        .order_by(MentorReview.created_at.desc())
        .all()
    )

    return MentorVersionDetailRead(
        version=_to_version_read(version),
        thesis=_to_thesis_read(version.thesis),
        latest_task=_build_task_read(task) if task else None,  # type: ignore[arg-type]
        reviews=[MentorReviewRead.model_validate(r) for r in reviews],
    )


@router.get("/reviews/{version_id}", response_model=list[MentorReviewRead])
def list_reviews_for_version(
    version_id: int,
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> list[MentorReviewRead]:
    version = db.get(ThesisVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found.")
    thesis = version.thesis
    if current_user.role == ROLE_MENTOR:
        bound_student_ids = _get_bound_student_ids(db, current_user.id)
        if not thesis or thesis.student_id not in bound_student_ids:
            raise HTTPException(status_code=403, detail="只能查看绑定学生的论文。")

    reviews = (
        db.query(MentorReview)
        .filter(MentorReview.version_id == version_id)
        .order_by(MentorReview.created_at.desc())
        .all()
    )
    return [MentorReviewRead.model_validate(r) for r in reviews]


@router.post("/reviews", response_model=MentorReviewSubmissionRead)
def submit_review(
    payload: MentorReviewCreate,
    current_user=Depends(require_mentor_scope),
    db: Session = Depends(get_db),
) -> MentorReviewSubmissionRead:
    version = db.get(ThesisVersion, payload.version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found.")

    thesis = version.thesis

    # Verify the thesis belongs to a student bound to this mentor
    # Admins and academics can review any thesis
    if current_user.role == ROLE_MENTOR:
        bound_student_ids = _get_bound_student_ids(db, current_user.id)
        if thesis.student_id not in bound_student_ids:
            raise HTTPException(status_code=403, detail="只能评审绑定学生的论文。")

    if thesis.status != THESIS_STATUS_MENTOR_REVIEW:
        raise HTTPException(status_code=400, detail="当前论文不在导师评审阶段，无法提交评审。")

    task = _get_latest_task(db, version.id)
    if not task or not task.student_ready_for_mentor:
        raise HTTPException(status_code=400, detail="当前版本尚未提交导师评审。")
    latest_version = _get_latest_version(thesis)
    if not latest_version or latest_version.id != version.id:
        raise HTTPException(status_code=400, detail="只能评审论文当前最新提交版本。")

    review = MentorReview(
        version_id=version.id,
        mentor_id=current_user.id,
        decision=payload.decision,
        comments=payload.comments,
    )
    db.add(review)

    if payload.decision == "approved":
        thesis.status = THESIS_STATUS_APPROVED
        version.stage = VERSION_STAGE_FINAL
    else:
        thesis.status = THESIS_STATUS_CHANGES_REQUESTED
        version.stage = VERSION_STAGE_REVISION

    notification_title = "导师评审结果"
    notification_body = (
        f"导师已通过你的论文《{thesis.title}》。"
        if payload.decision == "approved"
        else f"导师要求你修改论文《{thesis.title}》。"
    )
    if payload.comments:
        notification_body += f" 评审意见：{payload.comments}"

    db.add(
        Notification(
            user_id=thesis.student_id,
            title=notification_title,
            body=notification_body,
            is_read=False,
        )
    )

    db.commit()
    db.refresh(review)
    db.refresh(thesis)
    db.refresh(version)

    return MentorReviewSubmissionRead(
        review=MentorReviewRead.model_validate(review),
        thesis=_to_thesis_read(thesis),
        version=_to_version_read(version),
    )
