
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import (
    Student,
    StudyPlan,
    StudyPlanItem,
    Topic,
    Subject,
)
from app.api.dependencies import get_current_student
from app.schemas.study_plan_item_schema import (
    StudyPlanItemCreate,
    StudyPlanItemResponse,
    StudyPlanItemStatusUpdate,
)

router = APIRouter(
    prefix="/study-plan-items",
    tags=["Study Plan Items"],
)

ALLOWED_STATUSES = {
    "pending",
    "in_progress",
    "completed",
    "skipped",
}


def get_db():
    """Provide a database session for the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_owned_plan(
    plan_id: int,
    student_id: int,
    db: Session,
) -> StudyPlan:
    """Return a plan only if it belongs to the authenticated student."""
    plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.plan_id == plan_id,
            StudyPlan.student_id == student_id,
        )
        .first()
    )

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Study plan not found",
        )

    return plan


@router.post("/", response_model=StudyPlanItemResponse)
def create_study_plan_item(
    item: StudyPlanItemCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """Create an item only in the authenticated student's plan."""
    plan = get_owned_plan(
        item.plan_id,
        current_student.student_id,
        db,
    )

    if plan.status != "active":
        raise HTTPException(
            status_code=409,
            detail="Cannot add items to an inactive study plan",
        )

    topic = (
        db.query(Topic)
        .join(Subject, Topic.subject_id == Subject.subject_id)
        .filter(
            Topic.topic_id == item.topic_id,
            Subject.student_id == current_student.student_id,
        )
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=404,
            detail="Topic not found",
        )

    if item.duration_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail="Duration must be greater than 0",
        )

    if item.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Use: pending, in_progress, "
                "completed, or skipped"
            ),
        )

    new_item = StudyPlanItem(
        plan_id=plan.plan_id,
        topic_id=item.topic_id,
        scheduled_date=item.scheduled_date,
        duration_minutes=item.duration_minutes,
        priority=item.priority,
        status=item.status,
    )

    try:
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception:
        db.rollback()
        raise


@router.get(
    "/plan/{plan_id}",
    response_model=list[StudyPlanItemResponse],
)
def get_plan_items(
    plan_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """Return items only for the authenticated student's plan."""
    plan = get_owned_plan(
        plan_id,
        current_student.student_id,
        db,
    )

    return (
        db.query(StudyPlanItem)
        .filter(StudyPlanItem.plan_id == plan.plan_id)
        .order_by(
            StudyPlanItem.scheduled_date,
            StudyPlanItem.item_id,
        )
        .all()
    )


@router.put(
    "/{item_id}/status",
    response_model=StudyPlanItemResponse,
)
def update_item_status(
    item_id: int,
    status_update: StudyPlanItemStatusUpdate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """Update an item only if its plan belongs to this student."""
    item = (
        db.query(StudyPlanItem)
        .join(
            StudyPlan,
            StudyPlanItem.plan_id == StudyPlan.plan_id,
        )
        .filter(
            StudyPlanItem.item_id == item_id,
            StudyPlan.student_id == current_student.student_id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Study plan item not found",
        )

    if status_update.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Use: pending, in_progress, "
                "completed, or skipped"
            ),
        )

    plan = (
        db.query(StudyPlan)
        .filter(StudyPlan.plan_id == item.plan_id)
        .first()
    )

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Study plan not found",
        )

    if plan.status != "active":
        raise HTTPException(
            status_code=409,
            detail="Cannot update an item in an inactive study plan",
        )

    try:
        item.status = status_update.status
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise
