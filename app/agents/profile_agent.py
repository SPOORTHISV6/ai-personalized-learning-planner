
import logging

from app.database.connection import SessionLocal
from app.database.models import Student


logger = logging.getLogger(__name__)

SAFE_ERROR = "Student profile could not be loaded. Please try again later."


def profile_agent(state):
    print("\n[Profile Agent] Fetching student profile...")

    if not isinstance(state, dict):
        return {
            "errors": ["Invalid workflow state"],
            "next_action": "stop",
        }

    student_id = state.get("student_id")

    if (
        isinstance(student_id, bool)
        or not isinstance(student_id, int)
        or student_id <= 0
    ):
        return {
            "errors": ["A valid student ID is required"],
            "next_action": "stop",
        }

    db = None

    try:
        db = SessionLocal()

        student = (
            db.query(Student)
            .filter(Student.student_id == student_id)
            .first()
        )

        if not student:
            return {
                "errors": ["Student not found"],
                "next_action": "stop",
            }

        profile = {
            "student_id": student.student_id,
            "name": student.name,
            "email": student.email,
            "daily_available_hours": student.daily_available_hours,
            "learning_preference": student.learning_preference,
        }

        print(f"[Profile Agent] Student: {student.name}")

        return {
            "student_profile": profile,
            "next_action": "learning_gap",
        }

    except Exception:
        logger.exception(
            "Profile retrieval failed for student_id=%s",
            student_id,
        )

        return {
            "errors": [SAFE_ERROR],
            "next_action": "stop",
        }

    finally:
        if db is not None:
            db.close()
