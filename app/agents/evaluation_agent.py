
from sqlalchemy.exc import IntegrityError

from app.database.connection import SessionLocal
from app.database.models import (
    QuizResult,
    Quiz,
    Topic,
    Performance,
)
from app.agents.performance_rules import evaluate_score


DUPLICATE_PERFORMANCE_CONSTRAINT = "uq_performance_quiz_result_id"


def _is_duplicate_quiz_result_constraint(exc):
    """
    Return True only for a MySQL duplicate-key error naming the
    unique constraint that links performance to a quiz result.
    """
    original_error = exc.orig
    error_args = getattr(original_error, "args", ())

    if not error_args:
        return False

    try:
        error_code = int(error_args[0])
    except (TypeError, ValueError):
        return False

    return (
        error_code == 1062
        and DUPLICATE_PERFORMANCE_CONSTRAINT in str(original_error)
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

    quiz_result_id = state.get("quiz_result_id")
    expected_student_id = state.get("student_id")

    # 1. Validate the quiz result ID.
    if quiz_result_id is None:
        return {
            "errors": ["Quiz result ID is missing"],
            "next_action": "stop",
        }

    db = SessionLocal()

    try:
        # 2. Fetch the exact quiz result requested.
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

        # 3. Validate the student ID and ownership.
        if expected_student_id is None:
            return {
                "errors": ["Student ID is missing"],
                "next_action": "stop",
            }

        if quiz_result.student_id != expected_student_id:
            return {
                "errors": [
                    "Quiz result does not belong to the expected student"
                ],
                "next_action": "stop",
            }

        # 4. Fetch the quiz.
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

        # 5. Fetch the topic.
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

        # 6. Evaluate the score using shared performance rules.
        score = float(quiz_result.score)
        score_evaluation = evaluate_score(score)

        level = score_evaluation["level"]
        recommended_action = score_evaluation[
            "recommended_action"
        ]

        print(
            f"[Evaluation Agent] Quiz result ID: "
            f"{quiz_result.result_id}"
        )
        print(f"[Evaluation Agent] Topic: {topic.topic_name}")
        print(f"[Evaluation Agent] Score: {score}")
        print(f"[Evaluation Agent] Level: {level}")

        # 7. Find the performance record for this exact attempt.
        performance = (
            db.query(Performance)
            .filter(
                Performance.quiz_result_id
                == quiz_result.result_id
            )
            .first()
        )

        # 8. Create or update the performance record.
        if performance is None:
            performance = Performance(
                student_id=quiz_result.student_id,
                topic_id=quiz.topic_id,
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
            # Reuse the existing record for this exact attempt.
            performance.student_id = quiz_result.student_id
            performance.topic_id = quiz.topic_id
            performance.score = score
            performance.attempt_date = quiz_result.attempted_at

            print(
                "[Evaluation Agent] Existing performance "
                "record found. Updating it."
            )

        # Commit the change. If a concurrent request inserted the
        # same quiz-linked record first, recover only from that
        # specific MySQL duplicate-key constraint.
        try:
            db.commit()
            db.refresh(performance)

        except IntegrityError as exc:
            db.rollback()

            if not _is_duplicate_quiz_result_constraint(exc):
                raise

            # The competing transaction may have created the record.
            # Re-fetch it using a fresh transaction after the rollback.
            performance = (
                db.query(Performance)
                .filter(
                    Performance.quiz_result_id
                    == quiz_result.result_id
                )
                .first()
            )

            # Never report success if the expected record is absent.
            if performance is None:
                raise

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

        # 9. Build the evaluation result.
        evaluation = {
            "quiz_result_id": quiz_result.result_id,
            "student_id": quiz_result.student_id,
            "quiz_id": quiz.quiz_id,
            "topic_id": topic.topic_id,
            "topic_name": topic.topic_name,
            "score": score,
            "level": level,
            "recommended_action": recommended_action,
            "performance_id": performance.performance_id,
            "performance_recorded": True,
        }

        print("[Evaluation Agent] Evaluation completed.")

        # 10. Continue to the Reflection Agent.
        return {
            "evaluation": evaluation,
            "quiz_result_id": quiz_result.result_id,
            "next_action": "reflection",
        }

    except Exception as exc:
        db.rollback()

        print(f"[Evaluation Agent] Error: {str(exc)}")

        return {
            "errors": [
                f"Evaluation failed: {str(exc)}"
            ],
            "next_action": "stop",
        }

    finally:
        db.close()
