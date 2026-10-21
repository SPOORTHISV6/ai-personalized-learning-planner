
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Student, Subject, Topic
from app.api.dependencies import get_current_student
from app.schemas.topic_schema import (
    TopicCreate,
    TopicResponse,
)

router = APIRouter(
    prefix="/topics",
    tags=["Topics"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=TopicResponse)
def create_topic(
    topic: TopicCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    subject = (
        db.query(Subject)
        .filter(
            Subject.subject_id == topic.subject_id,
            Subject.student_id == current_student.student_id,
        )
        .first()
    )

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    if topic.prerequisite_topic_id is not None:
        prerequisite = (
            db.query(Topic)
            .filter(
                Topic.topic_id == topic.prerequisite_topic_id,
                Topic.subject_id == subject.subject_id,
            )
            .first()
        )

        if prerequisite is None:
            raise HTTPException(
                status_code=404,
                detail="Prerequisite topic not found in this subject.",
            )

    new_topic = Topic(
        subject_id=subject.subject_id,
        topic_name=topic.topic_name,
        difficulty=topic.difficulty,
        prerequisite_topic_id=topic.prerequisite_topic_id,
    )

    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    return new_topic


@router.get(
    "/subject/{subject_id}",
    response_model=list[TopicResponse],
)
def get_subject_topics(
    subject_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    subject = (
        db.query(Subject)
        .filter(Subject.subject_id == subject_id)
        .first()
    )

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    # Shared topics are allowed to be read; the subject must exist.
    return (
        db.query(Topic)
        .filter(Topic.subject_id == subject_id)
        .order_by(Topic.topic_id.asc())
        .all()
    )
