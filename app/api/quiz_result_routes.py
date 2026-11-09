
import logging
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    Quiz,
    QuizQuestion,
    QuizAnswer,
    QuizResult,
    Student,
    Topic,
    Subject,
)

from app.api.dependencies import get_current_student

from app.schemas.quiz_result_schema import (
    QuizSubmission,
    QuizResultResponse,
)

from app.workflows.adaptive_workflow import adaptive_workflow


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/quiz-results",
    tags=["Quiz Results"],
)


# =========================================================
# HELPER: VERIFY QUIZ OWNERSHIP
# =========================================================

def get_owned_quiz(
    db: Session,
    quiz_id: int,
    student_id: int,
):
    """
    Return a quiz only if its topic belongs to the student.

    Quiz -> Topic -> Subject -> Student

    Returns None for both nonexistent and unowned quizzes.
    This prevents quiz ID enumeration through different
    HTTP status codes.
    """

    return (
        db.query(Quiz)
        .join(
            Topic,
            Quiz.topic_id == Topic.topic_id,
        )
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(
            Quiz.quiz_id == quiz_id,
            Subject.student_id == student_id,
        )
        .first()
    )


# =========================================================
# HELPER: SANITIZE WORKFLOW ERRORS
# =========================================================

SAFE_WORKFLOW_ERROR = (
    "Adaptive learning could not be completed. "
    "Your quiz result was saved successfully."
)


def sanitize_workflow_payload(value: Any) -> Any:
    """
    Remove internal exception details from workflow output.

    Preserve normal evaluation and study-plan information,
    while replacing values under error-related keys.
    """

    sensitive_keys = {
        "error",
        "errors",
        "exception",
        "traceback",
    }

    if isinstance(value, Mapping):
        sanitized = {}

        for key, item in value.items():
            if str(key).lower() in sensitive_keys:
                sanitized[key] = SAFE_WORKFLOW_ERROR
            else:
                sanitized[key] = sanitize_workflow_payload(item)

        return sanitized

    if isinstance(value, list):
        return [
            sanitize_workflow_payload(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            sanitize_workflow_payload(item)
            for item in value
        )

    return value


# =========================================================
# SUBMIT QUIZ
# =========================================================

@router.post("/", response_model=dict)
def submit_quiz(
    submission: QuizSubmission,
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):

    sid = current_student.student_id

    # -----------------------------------------------------
    # 1. VERIFY QUIZ OWNERSHIP
    # -----------------------------------------------------

    # A nonexistent quiz and another student's quiz both
    # return 404 to prevent quiz ID enumeration.

    quiz = get_owned_quiz(
        db=db,
        quiz_id=quiz_id,
        student_id=sid,
    )

    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail="Quiz not found.",
        )

    # -----------------------------------------------------
    # 2. VERIFY STUDENT ID IN SUBMISSION
    # -----------------------------------------------------

    if submission.student_id != sid:
        raise HTTPException(
            status_code=403,
            detail="You cannot submit results for another student.",
        )

    # -----------------------------------------------------
    # 3. FETCH QUIZ QUESTIONS
    # -----------------------------------------------------

    questions = (
        db.query(QuizQuestion)
        .filter(
            QuizQuestion.quiz_id == quiz_id
        )
        .order_by(
            QuizQuestion.question_id
        )
        .all()
    )

    if not questions:
        raise HTTPException(
            status_code=400,
            detail="This quiz has no questions yet.",
        )

    # -----------------------------------------------------
    # 4. VALIDATE SUBMITTED ANSWERS
    # -----------------------------------------------------

    submitted_answers = {
        answer.question_id: answer.selected_option
        for answer in submission.answers
    }

    # Defensive duplicate validation. The Pydantic schema
    # also checks this before the route executes.

    if len(submitted_answers) != len(submission.answers):
        raise HTTPException(
            status_code=400,
            detail="Duplicate question answers are not allowed.",
        )

    expected_ids = {
        question.question_id
        for question in questions
    }

    submitted_ids = set(submitted_answers)

    unknown_ids = submitted_ids - expected_ids

    if unknown_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Some submitted questions do not belong "
                "to this quiz: "
                f"{sorted(unknown_ids)}"
            ),
        )

    unanswered_ids = expected_ids - submitted_ids

    if unanswered_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Answer every question before submitting. "
                f"Unanswered question IDs: "
                f"{sorted(unanswered_ids)}"
            ),
        )

    # -----------------------------------------------------
    # 5. CALCULATE SCORE
    # -----------------------------------------------------

    total_points = sum(
        question.points
        for question in questions
    )

    if total_points <= 0:
        raise HTTPException(
            status_code=400,
            detail="The quiz must have at least one point available.",
        )

    earned_points = 0
    graded_answers = []

    for question in questions:

        selected = submitted_answers[
            question.question_id
        ]

        correct = (
            selected == question.correct_option
        )

        awarded = (
            question.points if correct else 0
        )

        earned_points += awarded

        graded_answers.append(
            {
                "question_id": question.question_id,
                "selected_option": selected,
                "correct_option": question.correct_option,
                "is_correct": correct,
                "points_awarded": awarded,
                "maximum_points": question.points,
                "explanation": question.explanation,
            }
        )

    score = round(
        (earned_points / total_points) * 100,
        2,
    )

    # -----------------------------------------------------
    # 6. SAVE QUIZ RESULT AND ANSWERS
    # -----------------------------------------------------

    try:

        result = QuizResult(
            quiz_id=quiz_id,
            student_id=sid,
            score=score,
        )

        db.add(result)
        db.flush()

        for answer in graded_answers:

            db.add(
                QuizAnswer(
                    result_id=result.result_id,
                    question_id=answer["question_id"],
                    selected_option=answer["selected_option"],
                    is_correct=answer["is_correct"],
                    points_awarded=answer["points_awarded"],
                )
            )

        db.commit()
        db.refresh(result)

    except Exception as exc:

        db.rollback()

        logger.exception(
            "Failed to save quiz submission for student_id=%s, quiz_id=%s",
            sid,
            quiz_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to save the quiz submission.",
        ) from exc

    # -----------------------------------------------------
    # 7. RUN ADAPTIVE WORKFLOW
    # -----------------------------------------------------
    # The quiz result is already committed.
    # Workflow failure must not undo the saved result.
    # -----------------------------------------------------

    workflow_result = {}
    workflow_status = "failed"
    workflow_error = SAFE_WORKFLOW_ERROR
    errors = [SAFE_WORKFLOW_ERROR]

    try:

        raw_workflow_result = adaptive_workflow.invoke(
            {
                "student_id": sid,
                "quiz_result_id": result.result_id,
            }
        )

        if not isinstance(raw_workflow_result, Mapping):
            raise TypeError(
                "Adaptive workflow returned an invalid result."
            )

        raw_errors = raw_workflow_result.get(
            "errors",
            [],
        )

        if raw_errors is None:
            raw_errors = []

        if not isinstance(raw_errors, (list, tuple)):
            raw_errors = [raw_errors]

        sanitized_workflow_result = sanitize_workflow_payload(
            raw_workflow_result
        )

        workflow_result = dict(
            sanitized_workflow_result
        )

        if raw_errors:
            workflow_status = "completed_with_errors"
            workflow_error = SAFE_WORKFLOW_ERROR
            errors = [SAFE_WORKFLOW_ERROR]

        else:
            workflow_status = "completed"
            workflow_error = None
            errors = []

    except Exception:

        logger.exception(
            "Adaptive workflow failed for student_id=%s, "
            "quiz_result_id=%s",
            sid,
            result.result_id,
        )

        workflow_result = {}
        workflow_status = "failed"
        workflow_error = SAFE_WORKFLOW_ERROR
        errors = [SAFE_WORKFLOW_ERROR]

    # -----------------------------------------------------
    # 8. RETURN RESULT
    # -----------------------------------------------------

    return {
        "message": "Quiz submitted and graded.",
        "quiz_id": quiz_id,
        "quiz_title": quiz.title,
        "student_id": sid,
        "result_id": result.result_id,
        "score": score,
        "total_points": total_points,
        "earned_points": earned_points,
        "correct_answers": sum(
            1
            for answer in graded_answers
            if answer["is_correct"]
        ),
        "total_questions": len(questions),
        "answers": graded_answers,
        "workflow_status": workflow_status,
        "evaluation": workflow_result.get("evaluation"),
        "validation": workflow_result.get("validation"),
        "study_plan": workflow_result.get("persisted_plan"),
        "next_action": workflow_result.get("next_action"),
        "user_feedback": workflow_result.get("user_feedback"),
        "errors": errors,
        "workflow_error": workflow_error,
    }


# =========================================================
# GET STUDENT QUIZ RESULTS
# =========================================================

@router.get(
    "/student/{student_id}",
    response_model=list[QuizResultResponse],
)
def get_student_quiz_results(
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
        db.query(QuizResult)
        .filter(
            QuizResult.student_id == current_student.student_id
        )
        .order_by(
            QuizResult.attempted_at.desc()
        )
        .all()
    )


# =========================================================
# GET RESULTS FOR A PARTICULAR QUIZ
# =========================================================

@router.get(
    "/quiz/{quiz_id}",
    response_model=list[QuizResultResponse],
)
def get_quiz_results(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):

    # -----------------------------------------------------
    # 1. VERIFY QUIZ OWNERSHIP
    # -----------------------------------------------------

    quiz = get_owned_quiz(
        db=db,
        quiz_id=quiz_id,
        student_id=current_student.student_id,
    )

    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail="Quiz not found.",
        )

    # -----------------------------------------------------
    # 2. RETURN ONLY THIS STUDENT'S RESULTS
    # -----------------------------------------------------

    return (
        db.query(QuizResult)
        .filter(
            QuizResult.quiz_id == quiz_id,
            QuizResult.student_id == current_student.student_id,
        )
        .order_by(
            QuizResult.attempted_at.desc()
        )
        .all()
    )
