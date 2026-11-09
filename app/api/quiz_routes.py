
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database.connection import get_db
from app.database.models import (
    Quiz,
    QuizQuestion,
    Topic,
    Subject,
    Student,
)
from app.api.dependencies import get_current_student

from app.schemas.quiz_schema import (
    QuizCreate,
    QuizResponse,
    QuizQuestionCreate,
    QuizQuestionResponse,
    QuizQuestionAdminResponse,
)


router = APIRouter(
    prefix="/quizzes",
    tags=["Quizzes"],
)


# ============================================================
# STUDENT TOPIC OWNERSHIP VALIDATION
# ============================================================

def student_owns_topic(
    db: Session,
    topic_id: int,
    student_id: int,
) -> bool:
    """
    Check whether a topic belongs to the authenticated student.

    Relationship:
        Student -> Subject -> Topic
    """

    return (
        db.query(Topic.topic_id)
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(
            Topic.topic_id == topic_id,
            Subject.student_id == student_id,
        )
        .first()
        is not None
    )


# ============================================================
# ADMIN AUTHORIZATION
# ============================================================

def require_quiz_admin(
    current_student: Student = Depends(get_current_student),
) -> Student:
    """
    Allow quiz authoring only for accounts explicitly
    assigned the admin role in the database.
    """

    if current_student.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quiz authoring requires administrator permissions.",
        )

    return current_student


# ============================================================
# CREATE QUIZ
# ADMIN ONLY
# ============================================================

@router.post(
    "/",
    response_model=QuizResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_quiz(
    quiz_data: QuizCreate,
    db: Session = Depends(get_db),
    admin: Student = Depends(require_quiz_admin),
):
    """
    Create a quiz for an existing topic.

    Only administrators can create quizzes.
    """

    topic = (
        db.query(Topic)
        .filter(
            Topic.topic_id == quiz_data.topic_id
        )
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found.",
        )

    # Prevent accidental duplicate quiz creation.
    existing_quiz = (
        db.query(Quiz)
        .filter(
            Quiz.topic_id == quiz_data.topic_id,
            Quiz.title == quiz_data.title,
        )
        .first()
    )

    if existing_quiz is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A quiz with this title already exists for this topic.",
        )

    new_quiz = Quiz(
        topic_id=quiz_data.topic_id,
        title=quiz_data.title,
        difficulty=quiz_data.difficulty,
    )

    try:
        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create quiz.",
        ) from exc

    return {
        "quiz_id": new_quiz.quiz_id,
        "topic_id": new_quiz.topic_id,
        "title": new_quiz.title,
        "difficulty": new_quiz.difficulty,
        "created_at": new_quiz.created_at,
        "question_count": 0,
    }


# ============================================================
# GET QUIZZES FOR A TOPIC
# ============================================================

@router.get(
    "/topic/{topic_id}",
    response_model=list[QuizResponse],
)
def get_topic_quizzes(
    topic_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """
    Retrieve quizzes belonging to a particular topic.

    Students can access only their own topics.
    Administrators can access quizzes for all topics.
    """

    topic = (
        db.query(Topic)
        .filter(
            Topic.topic_id == topic_id
        )
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found.",
        )

    # Validate topic ownership for students.
    if (
        current_student.role != "admin"
        and not student_owns_topic(
            db,
            topic_id,
            current_student.student_id,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found for this student.",
        )

    quizzes = (
        db.query(Quiz)
        .options(
            joinedload(Quiz.questions)
        )
        .filter(
            Quiz.topic_id == topic_id
        )
        .order_by(
            Quiz.quiz_id.asc()
        )
        .all()
    )

    return [
        {
            "quiz_id": quiz.quiz_id,
            "topic_id": quiz.topic_id,
            "title": quiz.title,
            "difficulty": quiz.difficulty,
            "created_at": quiz.created_at,
            "question_count": len(quiz.questions),
        }
        for quiz in quizzes
        if len(quiz.questions) > 0
    ]


# ============================================================
# GET A SINGLE QUIZ
# ============================================================

@router.get(
    "/{quiz_id}",
    response_model=QuizResponse,
)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """
    Retrieve a single quiz.

    Students can retrieve only quizzes associated
    with their own topics.
    """

    quiz = (
        db.query(Quiz)
        .options(
            joinedload(Quiz.questions)
        )
        .filter(
            Quiz.quiz_id == quiz_id
        )
        .first()
    )

    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found.",
        )

    # Validate quiz ownership.
    if (
        current_student.role != "admin"
        and not student_owns_topic(
            db,
            quiz.topic_id,
            current_student.student_id,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found for this student.",
        )

    return {
        "quiz_id": quiz.quiz_id,
        "topic_id": quiz.topic_id,
        "title": quiz.title,
        "difficulty": quiz.difficulty,
        "created_at": quiz.created_at,
        "question_count": len(quiz.questions),
    }


# ============================================================
# ADD QUESTION TO A QUIZ
# ADMIN ONLY
# ============================================================

@router.post(
    "/{quiz_id}/questions",
    response_model=QuizQuestionAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_quiz_question(
    quiz_id: int,
    question_data: QuizQuestionCreate,
    db: Session = Depends(get_db),
    admin: Student = Depends(require_quiz_admin),
):
    """
    Add a question to an existing quiz.

    Only administrators can add questions.
    Correct answers are stored in the database but
    are not exposed through the student endpoint.
    """

    quiz = (
        db.query(Quiz)
        .filter(
            Quiz.quiz_id == quiz_id
        )
        .first()
    )

    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found.",
        )

    question = QuizQuestion(
        quiz_id=quiz_id,
        question_text=question_data.question_text,
        option_a=question_data.option_a,
        option_b=question_data.option_b,
        option_c=question_data.option_c,
        option_d=question_data.option_d,
        correct_option=question_data.correct_option,
        explanation=question_data.explanation,
        points=question_data.points,
    )

    try:
        db.add(question)
        db.commit()
        db.refresh(question)

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add quiz question.",
        ) from exc

    return question


# ============================================================
# GET QUESTIONS FOR A QUIZ
# CORRECT ANSWERS ARE NOT EXPOSED
# ============================================================

@router.get(
    "/{quiz_id}/questions",
    response_model=list[QuizQuestionResponse],
)
def get_quiz_questions(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """
    Retrieve questions for a quiz.

    Students can retrieve questions only from their own quizzes.

    Correct answers are never returned.
    """

    quiz = (
        db.query(Quiz)
        .filter(
            Quiz.quiz_id == quiz_id
        )
        .first()
    )

    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found.",
        )

    # Validate quiz ownership.
    if (
        current_student.role != "admin"
        and not student_owns_topic(
            db,
            quiz.topic_id,
            current_student.student_id,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found for this student.",
        )

    questions = (
        db.query(QuizQuestion)
        .filter(
            QuizQuestion.quiz_id == quiz_id
        )
        .order_by(
            QuizQuestion.question_id.asc()
        )
        .all()
    )

    return [
        {
            "question_id": question.question_id,
            "quiz_id": question.quiz_id,
            "question_text": question.question_text,
            "option_a": question.option_a,
            "option_b": question.option_b,
            "option_c": question.option_c,
            "option_d": question.option_d,
            "explanation": question.explanation,
            "points": question.points,
        }
        for question in questions
    ]
