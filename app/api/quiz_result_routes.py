
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    Quiz,
    QuizQuestion,
    QuizAnswer,
    QuizResult,
    Student,
)
from app.api.dependencies import get_current_student
from app.schemas.quiz_result_schema import (
    QuizSubmission,
    QuizResultResponse,
)
from app.workflows.adaptive_workflow import adaptive_workflow

router = APIRouter(
    prefix="/quiz-results",
    tags=["Quiz Results"],
)


@router.post("/", response_model=dict)
def submit_quiz(
    submission: QuizSubmission,
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    sid = current_student.student_id

    # Validate quiz.
    quiz = (
        db.query(Quiz)
        .filter(Quiz.quiz_id == quiz_id)
        .first()
    )
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    # Do not trust a student ID supplied in the request body.
    if submission.student_id != sid:
        raise HTTPException(
            status_code=403,
            detail="You cannot submit results for another student.",
        )

    questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.question_id)
        .all()
    )
    if not questions:
        raise HTTPException(
            status_code=400,
            detail="This quiz has no questions yet.",
        )

    submitted_answers = {
        answer.question_id: answer.selected_option
        for answer in submission.answers
    }
    expected_ids = {q.question_id for q in questions}
    submitted_ids = set(submitted_answers)

    unknown_ids = submitted_ids - expected_ids
    if unknown_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Some submitted questions do not belong to this quiz: "
                f"{sorted(unknown_ids)}"
            ),
        )

    unanswered_ids = expected_ids - submitted_ids
    if unanswered_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Answer every question before submitting. "
                f"Unanswered question IDs: {sorted(unanswered_ids)}"
            ),
        )

    total_points = sum(q.points for q in questions)
    if total_points <= 0:
        raise HTTPException(
            status_code=400,
            detail="The quiz must have at least one point available.",
        )

    earned_points = 0
    graded_answers = []

    for question in questions:
        selected = submitted_answers[question.question_id]
        correct = selected == question.correct_option
        awarded = question.points if correct else 0
        earned_points += awarded

        graded_answers.append({
            "question_id": question.question_id,
            "selected_option": selected,
            "correct_option": question.correct_option,
            "is_correct": correct,
            "points_awarded": awarded,
            "maximum_points": question.points,
            "explanation": question.explanation,
        })

    score = round((earned_points / total_points) * 100, 2)

    try:
        result = QuizResult(
            quiz_id=quiz_id,
            student_id=sid,
            score=score,
        )
        db.add(result)
        db.flush()

        for answer in graded_answers:
            db.add(QuizAnswer(
                result_id=result.result_id,
                question_id=answer["question_id"],
                selected_option=answer["selected_option"],
                is_correct=answer["is_correct"],
                points_awarded=answer["points_awarded"],
            ))

        db.commit()
        db.refresh(result)

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save the quiz submission.",
        ) from exc

    # Preserve the adaptive workflow and target the exact result just saved.
    try:
        workflow_result = adaptive_workflow.invoke({
            "student_id": sid,
            "quiz_result_id": result.result_id,
        })
        errors = workflow_result.get("errors", [])
        workflow_status = (
            "completed" if not errors else "completed_with_errors"
        )
        workflow_error = None
    except Exception as exc:
        workflow_result = {}
        workflow_status = "failed"
        workflow_error = str(exc)
        errors = [workflow_error]

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
            1 for answer in graded_answers if answer["is_correct"]
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
        .filter(QuizResult.student_id == current_student.student_id)
        .order_by(QuizResult.attempted_at.desc())
        .all()
    )


@router.get(
    "/quiz/{quiz_id}",
    response_model=list[QuizResultResponse],
)
def get_quiz_results(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    # Students may view only their own results for a given quiz.
    quiz = (
        db.query(Quiz)
        .filter(Quiz.quiz_id == quiz_id)
        .first()
    )
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    return (
        db.query(QuizResult)
        .filter(
            QuizResult.quiz_id == quiz_id,
            QuizResult.student_id == current_student.student_id,
        )
        .order_by(QuizResult.attempted_at.desc())
        .all()
    )
