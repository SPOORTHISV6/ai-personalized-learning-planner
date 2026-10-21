
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Student, Subject
from app.api.dependencies import get_current_student
from app.schemas.subject_schema import (
    SubjectCreate,
    SubjectResponse,
)

router = APIRouter(
    prefix="/subjects",
    tags=["Subjects"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=SubjectResponse)
def create_subject(
    subject: SubjectCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    if subject.student_id != current_student.student_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot create subjects for another student.",
        )

    new_subject = Subject(
        student_id=current_student.student_id,
        subject_name=subject.subject_name,
        exam_date=subject.exam_date,
        importance=subject.importance,
    )

    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)
    return new_subject


@router.get(
    "/student/{student_id}",
    response_model=list[SubjectResponse],
)
def get_student_subjects(
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
        db.query(Subject)
        .filter(Subject.student_id == current_student.student_id)
        .order_by(Subject.subject_id.asc())
        .all()
    )
