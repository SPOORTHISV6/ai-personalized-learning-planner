
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Student, StudyPlan
from app.api.dependencies import get_current_student
from app.schemas.study_plan_schema import (
    StudyPlanCreate,
    StudyPlanResponse,
)

router = APIRouter(
    prefix="/study-plans",
    tags=["Study Plans"],
)


@router.post(
    "/",
    response_model=StudyPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_study_plan(
    plan: StudyPlanCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    # Never allow a user to create a plan for another student.
    if plan.student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create a study plan for another student.",
        )

    if plan.end_date <= plan.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date.",
        )

    requested_status = (plan.status or "active").strip().lower()

    if requested_status not in {
        "active",
        "superseded",
        "completed",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be active, superseded, or completed.",
        )

    try:
        # Preserve the one-active-plan-per-student behavior.
        if requested_status == "active":
            active_plans = (
                db.query(StudyPlan)
                .filter(
                    StudyPlan.student_id == current_student.student_id,
                    StudyPlan.status == "active",
                )
                .all()
            )

            for old_plan in active_plans:
                old_plan.status = "superseded"

        new_plan = StudyPlan(
            student_id=current_student.student_id,
            start_date=plan.start_date,
            end_date=plan.end_date,
            status=requested_status,
        )

        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        return new_plan

    except Exception:
        db.rollback()
        raise


@router.get(
    "/student/{student_id}",
    response_model=list[StudyPlanResponse],
)
def get_student_plans(
    student_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    if student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another student's study plans.",
        )

    return (
        db.query(StudyPlan)
        .filter(
            StudyPlan.student_id == current_student.student_id
        )
        .order_by(
            StudyPlan.created_at.desc(),
            StudyPlan.plan_id.desc(),
        )
        .all()
    )


@router.get(
    "/student/{student_id}/active",
    response_model=StudyPlanResponse,
)
def get_active_study_plan(
    student_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    if student_id != current_student.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another student's study plans.",
        )

    active_plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.student_id == current_student.student_id,
            StudyPlan.status == "active",
        )
        .order_by(
            StudyPlan.created_at.desc(),
            StudyPlan.plan_id.desc(),
        )
        .first()
    )

    if active_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active study plan found.",
        )

    return active_plan


@router.get(
    "/{plan_id}",
    response_model=StudyPlanResponse,
)
def get_study_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    study_plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.plan_id == plan_id,
            StudyPlan.student_id == current_student.student_id,
        )
        .first()
    )

    if study_plan is None:
        # Do not reveal whether another student's plan exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study plan not found.",
        )

    return study_plan
