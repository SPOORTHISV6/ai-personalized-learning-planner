from app.database.connection import SessionLocal
from app.database.models import Student


def profile_agent(state):

    print("\n[Profile Agent] Fetching student profile...")

    student_id = state["student_id"]

    db = SessionLocal()

    try:

        student = (
            db.query(Student)
            .filter(Student.student_id == student_id)
            .first()
        )

        if not student:

            return {
                "errors": [f"Student {student_id} not found"],
                "next_action": "stop"
            }

        profile = {
            "student_id": student.student_id,
            "name": student.name,
            "email": student.email,
            "daily_available_hours": student.daily_available_hours,
            "learning_preference": student.learning_preference
        }

        print(
            f"[Profile Agent] Student: {student.name}"
        )

        return {
            "student_profile": profile,
            "next_action": "learning_gap"
        }

    finally:
        db.close()