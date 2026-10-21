
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database.connection import get_db
from app.database.models import Quiz, QuizQuestion, Topic, Student
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


def require_quiz_admin(
    current_student: Student = Depends(get_current_student),
) -> Student:
    # No administrator role is currently defined in the supplied model.
    # Fail closed instead of allowing every authenticated student to edit quizzes.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Quiz authoring requires administrator permissions.",
    )


@router.post("/", response_model=QuizResponse, status_code=201)
def create_quiz(
    quiz_data: QuizCreate,
    db: Session = Depends(get_db),
    admin: Student = Depends(require_quiz_admin),
):
    topic = (
        db.query(Topic)
        .filter(Topic.topic_id == quiz_data.topic_id)
        .first()
    )

    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    new_quiz = Quiz(
        topic_id=quiz_data.topic_id,
        title=quiz_data.title,
        difficulty=quiz_data.difficulty,
    )

    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    return {
        "quiz_id": new_quiz.quiz_id,
        "topic_id": new_quiz.topic_id,
        "title": new_quiz.title,
        "difficulty": new_quiz.difficulty,
        "created_at": new_quiz.created_at,
        "question_count": 0,
    }


@router.get("/topic/{topic_id}", response_model=list[QuizResponse])
def get_topic_quizzes(
    topic_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    topic = (
        db.query(Topic)
        .filter(Topic.topic_id == topic_id)
        .first()
    )

    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    quizzes = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions))
        .filter(Quiz.topic_id == topic_id)
        .order_by(Quiz.quiz_id.asc())
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
    ]


@router.get("/{quiz_id}", response_model=QuizResponse)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions))
        .filter(Quiz.quiz_id == quiz_id)
        .first()
    )

    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    return {
        "quiz_id": quiz.quiz_id,
        "topic_id": quiz.topic_id,
        "title": quiz.title,
        "difficulty": quiz.difficulty,
        "created_at": quiz.created_at,
        "question_count": len(quiz.questions),
    }


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
    quiz = (
        db.query(Quiz)
        .filter(Quiz.quiz_id == quiz_id)
        .first()
    )

    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

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

    db.add(question)
    db.commit()
    db.refresh(question)

    return question


@router.get(
    "/{quiz_id}/questions",
    response_model=list[QuizQuestionResponse],
)
def get_quiz_questions(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    quiz = (
        db.query(Quiz)
        .filter(Quiz.quiz_id == quiz_id)
        .first()
    )

    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.question_id.asc())
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
            "explanation": None,
            "points": question.points,
        }
        for question in questions
    ]
