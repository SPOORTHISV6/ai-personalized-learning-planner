
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.api.dependencies import get_current_student
from app.database.connection import get_db
from app.database.models import Student
from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    AuthenticatedStudent,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=AuthenticatedStudent,
    status_code=status.HTTP_201_CREATED,
)
def register_student(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_student = (
        db.query(Student)
        .filter(Student.email == str(request.email))
        .first()
    )

    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    student = Student(
        name=request.name.strip(),
        email=str(request.email),
        password_hash=hash_password(request.password),
        daily_available_hours=request.daily_available_hours,
        learning_preference=request.learning_preference,
    )

    try:
        db.add(student)
        db.commit()
        db.refresh(student)
    except Exception:
        db.rollback()
        raise

    return student


@router.post("/login", response_model=TokenResponse)
def login_student(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.email == str(request.email))
        .first()
    )

    # Existing students with NULL password_hash must first complete
    # a secure password setup process.
    if (
        student is None
        or not student.password_hash
        or not verify_password(
            request.password,
            student.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(student.student_id)

    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=AuthenticatedStudent)
def get_authenticated_student(
    student: Student = Depends(get_current_student),
):
    return student
