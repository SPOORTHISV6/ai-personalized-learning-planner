
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_student
from app.database.connection import SessionLocal
from app.database.models import Student
from app.schemas.student_schema import StudentResponse


router = APIRouter(
    prefix="/students",
    tags=["Students"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------
# GET AUTHENTICATED STUDENT PROFILE
# --------------------------------------------------

@router.get("/me", response_model=StudentResponse)
def get_my_profile(
    current_student: Student = Depends(get_current_student),
):
    return current_student


# --------------------------------------------------
# GET STUDENT BY ID: OWN PROFILE ONLY
# --------------------------------------------------

@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    # Return 404 for other IDs to avoid revealing
    # whether another student's account exists.
    if current_student.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    student = (
        db.query(Student)
        .filter(Student.student_id == current_student.student_id)
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    return student
