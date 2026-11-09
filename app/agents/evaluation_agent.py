import logging
import re

from sqlalchemy.exc import IntegrityError

from app.database.connection import SessionLocal
from app.database.models import (
    QuizResult,
    Quiz,
    Topic,
    Subject,
    Performance,
)
from app.agents.performance_rules import evaluate_score


logger = logging.getLogger(__name__)

DUPLICATE_PERFORMANCE_CONSTRAINT = "uq_performance_quiz_result_id"

SAFE_EVALUATION_ERROR = (
    "Evaluation could not be completed. "
    "Please try again later."
)

MAX_TOPIC_NAME_LENGTH = 150


def _is_positive_integer(value):
    """
    Validate a positive integer ID.

    Boolean values are rejected because bool is a subclass of int.
    """

    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def _sanitize_topic_name(value):
    """
    Remove control characters and normalize whitespace in topic names.
    """

    if not isinstance(value, str):
        return "Unknown topic"

    sanitized = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    sanitized = " ".join(sanitized.split())

    if not sanitized:
        return "Unknown topic"

    return sanitized[:MAX_TOPIC_NAME_LENGTH]


def _is_duplicate_quiz_result_constraint(exc):
    """
    Return True only for a MySQL duplicate-key error naming the
    unique constraint that links performance to a quiz result.
    """

    original_error = getattr(exc, "orig", None)

    if original_error is None:
        return False

    error_args = getattr(original_error, "args", ())

    if not error_args:
        return False

    try:
        error_code = int(error_args[0])
    except (TypeError, ValueError, OverflowError):
        return False

    return (
        error_code == 1062
        and DUPLICATE_PERFORMANCE_CONSTRAINT
        in str(original_error)
    )


def _has_correct_performance_ownership(
    performance,
    student_id,
    topic_id,
    quiz_result_id,
):
    """
    Verify that a performance record belongs to the exact student,
    topic, and quiz result being evaluated.
    """

    if performance is None:
        return False

    return (
        performance.student_id == student_id
        and performance.topic_id == topic_id
        and performance.quiz_result_id == quiz_result_id
    )


def _rollback_safely(db):
    """
    Attempt rollback without allowing cleanup errors to hide the
    original database failure.
    """

    if db is None:
        return

    try:
        db.rollback()
    except Exception:
        logger.exception(
            "Database rollback failed during evaluation cleanup."
        )


def evaluation_agent(state):
    """
    Evaluate a specific quiz result, persist its performance record,
    and pass the evaluation to the Reflection Agent.

    Expected state:
        {
            "student_id": int,
            "quiz_result_id": int,
        }

    Returns:
        Evaluation details and next_action="reflection" on success.
        An errors list and next_action="stop" on failure.
    """

    print("\n[Evaluation Agent] Evaluating quiz performance...")

    # 1. Validate workflow state.
    if not isinstance(state, dict):
        return {
            "errors": ["Invalid evaluation workflow state"],
            "next_action": "stop",
        }

    quiz_result_id = state.get("quiz_result_id")
    expected_student_id = state.get("student_id")

    if quiz_result_id is None:
        return {
            "errors": ["Quiz result ID is missing"],
            "next_action": "stop",
        }

    if not _is_positive_integer(quiz_result_id):
        return {
            "errors": ["Invalid quiz result ID"],
            "next_action": "stop",
        }

    db = None

    try:
        db = SessionLocal()

        # 2. Fetch the exact quiz result first.
        # Preserve not-found behavior even when student_id is missing.
        quiz_result = (
            db.query(QuizResult)
            .filter(QuizResult.result_id == quiz_result_id)
            .first()
        )

        if quiz_result is None:
            return {
                "errors": [
                    f"Quiz result {quiz_result_id} not found"
                ],
                "next_action": "stop",
            }

        # 3. Validate the expected student ID.
        if expected_student_id is None:
            return {
                "errors": ["Student ID is missing"],
                "next_action": "stop",
            }

        if not _is_positive_integer(expected_student_id):
            return {
                "errors": ["Invalid student ID"],
                "next_action": "stop",
            }

        # 4. Verify quiz-result ownership.
        if quiz_result.student_id != expected_student_id:
            return {
                "errors": [
                    "Quiz result does not belong to the expected student"
                ],
                "next_action": "stop",
            }

        # 5. Fetch the quiz associated with this exact result.
        quiz = (
            db.query(Quiz)
            .filter(Quiz.quiz_id == quiz_result.quiz_id)
            .first()
        )

        if quiz is None:
            return {
                "errors": [
                    f"Quiz {quiz_result.quiz_id} not found"
                ],
                "next_action": "stop",
            }

        # 6. Fetch the topic associated with the quiz.
        topic = (
            db.query(Topic)
            .filter(Topic.topic_id == quiz.topic_id)
            .first()
        )

        if topic is None:
            return {
                "errors": [
                    f"Topic {quiz.topic_id} not found"
                ],
                "next_action": "stop",
            }

        # 7. Verify that the topic's subject belongs to this student.
        subject = (
            db.query(Subject)
            .filter(
                Subject.subject_id == topic.subject_id,
                Subject.student_id == expected_student_id,
            )
            .first()
        )

        if subject is None:
            return {
                "errors": [
                    "Quiz topic does not belong to the expected student"
                ],
                "next_action": "stop",
            }

        # 8. Validate the original score before converting it.
        # This prevents bool values such as True from becoming 1.0.
        score_evaluation = evaluate_score(quiz_result.score)

        score = float(quiz_result.score)

        level = score_evaluation["level"]
        recommended_action = score_evaluation[
            "recommended_action"
        ]

        safe_topic_name = _sanitize_topic_name(topic.topic_name)

        print(
            f"[Evaluation Agent] Quiz result ID: "
            f"{quiz_result.result_id}"
        )
        print(f"[Evaluation Agent] Topic: {safe_topic_name}")
        print(f"[Evaluation Agent] Score: {score}")
        print(f"[Evaluation Agent] Level: {level}")

        # 9. Find the performance record for this exact attempt.
        performance = (
            db.query(Performance)
            .filter(
                Performance.quiz_result_id
                == quiz_result.result_id
            )
            .first()
        )

        # 10. Create or safely reuse the performance record.
        if performance is None:
            performance = Performance(
                student_id=quiz_result.student_id,
                topic_id=topic.topic_id,
                quiz_result_id=quiz_result.result_id,
                score=score,
                attempt_date=quiz_result.attempted_at,
            )

            db.add(performance)

            print(
                "[Evaluation Agent] Creating a new "
                "performance record."
            )

        else:
            # Never silently reassign an existing historical record.
            if not _has_correct_performance_ownership(
                performance=performance,
                student_id=expected_student_id,
                topic_id=topic.topic_id,
                quiz_result_id=quiz_result.result_id,
            ):
                logger.error(
                    "Performance ownership mismatch detected. "
                    "Quiz result ID: %s, expected student ID: %s, "
                    "stored student ID: %s, expected topic ID: %s, "
                    "stored topic ID: %s",
                    quiz_result.result_id,
                    expected_student_id,
                    performance.student_id,
                    topic.topic_id,
                    performance.topic_id,
                )

                return {
                    "errors": [
                        "Existing performance record has an "
                        "ownership mismatch"
                    ],
                    "next_action": "stop",
                }

            # Reuse the existing record only after ownership validation.
            # Preserve the existing update behavior.
            performance.score = score
            performance.attempt_date = quiz_result.attempted_at

            print(
                "[Evaluation Agent] Existing performance "
                "record found. Updating it."
            )

        # 11. Commit the change.
        # Recover only from the specific duplicate-key constraint.
        try:
            db.commit()
            db.refresh(performance)

        except IntegrityError as exc:
            _rollback_safely(db)

            if not _is_duplicate_quiz_result_constraint(exc):
                raise

            # Another request may have inserted this exact record.
            performance = (
                db.query(Performance)
                .filter(
                    Performance.quiz_result_id
                    == quiz_result.result_id
                )
                .first()
            )

            if performance is None:
                raise

            # Validate the recovered record before reporting success.
            if not _has_correct_performance_ownership(
                performance=performance,
                student_id=expected_student_id,
                topic_id=topic.topic_id,
                quiz_result_id=quiz_result.result_id,
            ):
                logger.error(
                    "Concurrent performance recovery returned "
                    "an ownership mismatch for quiz result ID %s",
                    quiz_result.result_id,
                )

                return {
                    "errors": [
                        "Existing performance record has an "
                        "ownership mismatch"
                    ],
                    "next_action": "stop",
                }

            db.refresh(performance)

            print(
                "[Evaluation Agent] Concurrent evaluation detected. "
                "Reusing performance record "
                f"{performance.performance_id}."
            )

        print(
            "[Evaluation Agent] Performance record saved. "
            f"ID: {performance.performance_id}"
        )

        # 12. Build the evaluation result.
        evaluation = {
            "quiz_result_id": quiz_result.result_id,
            "student_id": quiz_result.student_id,
            "quiz_id": quiz.quiz_id,
            "topic_id": topic.topic_id,
            "topic_name": safe_topic_name,
            "score": score,
            "level": level,
            "recommended_action": recommended_action,
            "performance_id": performance.performance_id,
            "performance_recorded": True,
        }

        print("[Evaluation Agent] Evaluation completed.")

        # 13. Continue to the Reflection Agent.
        return {
            "evaluation": evaluation,
            "quiz_result_id": quiz_result.result_id,
            "next_action": "reflection",
        }

    except Exception:
        _rollback_safely(db)

        # Detailed exception stays in server logs.
        logger.exception(
            "Evaluation agent failed for quiz result ID: %s",
            quiz_result_id,
        )

        return {
            "errors": [SAFE_EVALUATION_ERROR],
            "next_action": "stop",
        }

    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception(
                    "Failed to close the Evaluation Agent database session."
                )