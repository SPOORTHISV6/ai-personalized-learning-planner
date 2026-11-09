
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    Student,
    Subject,
    Topic,
    Performance,
    StudyPlan,
    StudyPlanItem,
)
from app.api.dependencies import get_current_student


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/student/{student_id}")
def get_student_dashboard(
    student_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    # A student can access only their own dashboard.
    if student_id != current_student.student_id:
        raise HTTPException(
            status_code=404,
            detail="Student not found.",
        )

    student = (
        db.query(Student)
        .filter(
            Student.student_id == current_student.student_id
        )
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found.",
        )

    sid = current_student.student_id

    # ---------------------------------------------------------
    # SUBJECT AND TOPIC COUNTS
    # ---------------------------------------------------------

    total_subjects = (
        db.query(Subject)
        .filter(Subject.student_id == sid)
        .count()
    )

    total_topics = (
        db.query(Topic)
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(Subject.student_id == sid)
        .count()
    )

    # ---------------------------------------------------------
    # PERFORMANCE STATISTICS
    # Include only performance records whose topics belong
    # to the authenticated student.
    # ---------------------------------------------------------

    performances = (
        db.query(Performance)
        .join(
            Topic,
            Performance.topic_id == Topic.topic_id,
        )
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(
            Performance.student_id == sid,
            Subject.student_id == sid,
        )
        .order_by(
            Performance.attempt_date.desc(),
            Performance.performance_id.desc(),
        )
        .all()
    )

    latest_scores = {}

    for performance in performances:
        if performance.topic_id not in latest_scores:
            latest_scores[performance.topic_id] = float(
                performance.score
            )

    scores = list(latest_scores.values())

    average_score = (
        round(sum(scores) / len(scores), 2)
        if scores else 0.0
    )

    weak_topics = sum(score < 50 for score in scores)

    moderate_topics = sum(
        50 <= score < 75
        for score in scores
    )

    strong_topics = sum(
        score >= 75
        for score in scores
    )

    # ---------------------------------------------------------
    # ACTIVE STUDY PLAN
    # ---------------------------------------------------------

    active_plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.student_id == sid,
            StudyPlan.status == "active",
        )
        .order_by(StudyPlan.created_at.desc())
        .first()
    )

    # Include only active-plan items linked to the student's
    # own topics.
    active_items = []

    if active_plan:
        active_items = (
            db.query(StudyPlanItem)
            .join(
                Topic,
                StudyPlanItem.topic_id == Topic.topic_id,
            )
            .join(
                Subject,
                Topic.subject_id == Subject.subject_id,
            )
            .filter(
                StudyPlanItem.plan_id == active_plan.plan_id,
                Subject.student_id == sid,
            )
            .all()
        )

    active_completed = sum(
        1 for item in active_items
        if (item.status or "pending").lower() == "completed"
    )

    active_pending = sum(
        1 for item in active_items
        if (item.status or "pending").lower() == "pending"
    )

    active_in_progress = sum(
        1 for item in active_items
        if (item.status or "pending").lower() == "in_progress"
    )

    # ---------------------------------------------------------
    # OVERALL STUDY PLAN STATISTICS
    # Include only plans and topics belonging to this student.
    # ---------------------------------------------------------

    all_items = (
        db.query(StudyPlanItem)
        .join(
            StudyPlan,
            StudyPlanItem.plan_id == StudyPlan.plan_id,
        )
        .join(
            Topic,
            StudyPlanItem.topic_id == Topic.topic_id,
        )
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(
            StudyPlan.student_id == sid,
            Subject.student_id == sid,
        )
        .all()
    )

    overall_completed = sum(
        1 for item in all_items
        if (item.status or "").lower() == "completed"
    )

    overall_pending = sum(
        1 for item in all_items
        if (item.status or "").lower() == "pending"
    )

    overall_in_progress = sum(
        1 for item in all_items
        if (item.status or "").lower() == "in_progress"
    )

    # ---------------------------------------------------------
    # RESPONSE
    # Preserve the existing dashboard response structure.
    # ---------------------------------------------------------

    return {
        "student_id": student.student_id,
        "student_name": student.name,
        "total_subjects": total_subjects,
        "total_topics": total_topics,
        "average_score": average_score,
        "weak_topics": weak_topics,
        "moderate_topics": moderate_topics,
        "strong_topics": strong_topics,
        "active_study_plans": 1 if active_plan else 0,
        "active_plan_id": (
            active_plan.plan_id if active_plan else None
        ),
        "active_total_sessions": len(active_items),
        "active_completed_sessions": active_completed,
        "active_pending_sessions": active_pending,
        "active_in_progress_sessions": active_in_progress,
        "overall_completed_sessions": overall_completed,
        "overall_pending_sessions": overall_pending,
        "overall_in_progress_sessions": overall_in_progress,
        "completed_sessions": active_completed,
        "pending_sessions": active_pending,
    }
