
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Student, Subject, Topic, Performance
from app.api.dependencies import get_current_student
from app.schemas.performance_schema import (
    PerformanceCreate,
    PerformanceResponse,
)

router = APIRouter(
    prefix="/performance",
    tags=["Performance"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=PerformanceResponse)
def create_performance(
    performance: PerformanceCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    # Never allow the request body to select another student.
    if performance.student_id != current_student.student_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot create performance records for another student.",
        )

    student = (
        db.query(Student)
        .filter(Student.student_id == current_student.student_id)
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found.",
        )

    # Verify that the topic belongs to this student's subject.
    topic = (
        db.query(Topic)
        .join(Subject, Topic.subject_id == Subject.subject_id)
        .filter(
            Topic.topic_id == performance.topic_id,
            Subject.student_id == current_student.student_id,
        )
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=404,
            detail="Topic not found.",
        )

    new_performance = Performance(
        student_id=current_student.student_id,
        topic_id=performance.topic_id,
        score=performance.score,
    )

    db.add(new_performance)
    db.commit()
    db.refresh(new_performance)

    return new_performance


@router.get(
    "/student/{student_id}",
    response_model=list[PerformanceResponse],
)
def get_student_performance(
    student_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    if student_id != current_student.student_id:
        raise HTTPException(
            status_code=404,
            detail="Student not found.",
        )

    return (
        db.query(Performance)
        .filter(
            Performance.student_id == current_student.student_id
        )
        .order_by(
            Performance.attempt_date.desc(),
            Performance.performance_id.desc(),
        )
        .all()
    )


@router.get(
    "/topic/{topic_id}",
    response_model=list[PerformanceResponse],
)
def get_topic_performance(
    topic_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    topic = (
        db.query(Topic)
        .join(Subject, Topic.subject_id == Subject.subject_id)
        .filter(
            Topic.topic_id == topic_id,
            Subject.student_id == current_student.student_id,
        )
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=404,
            detail="Topic not found.",
        )

    return (
        db.query(Performance)
        .filter(
            Performance.topic_id == topic_id,
            Performance.student_id == current_student.student_id,
        )
        .order_by(
            Performance.attempt_date.desc(),
            Performance.performance_id.desc(),
        )
        .all()
    )
