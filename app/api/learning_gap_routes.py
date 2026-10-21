
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Student
from app.api.dependencies import get_current_student
from app.tools.learning_gap import calculate_learning_gaps
from app.schemas.learning_gap_schema import LearningGapResponse

router = APIRouter(
    prefix="/learning-gaps",
    tags=["Learning Gaps"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/student/{student_id}",
    response_model=list[LearningGapResponse],
)
def get_learning_gaps(
    student_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    if student_id != current_student.student_id:
        raise HTTPException(
            status_code=404,
            detail="Student not found.",
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

    return calculate_learning_gaps(
        current_student.student_id,
        db,
    )
