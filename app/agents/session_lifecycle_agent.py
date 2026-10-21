
from datetime import date, datetime, time

from app.database.connection import SessionLocal
from app.database.models import StudyPlan, StudyPlanItem


VALID_STATUSES = {"pending", "overdue", "completed"}


def detect_overdue_sessions(student_id, today=None):
    """
    Mark pending sessions overdue when their scheduled date
    is earlier than today.

    Only active study plans are updated. Historical plans and
    completed sessions are left untouched.
    """
    today = today or date.today()
    db = SessionLocal()

    try:
        sessions = (
            db.query(StudyPlanItem)
            .join(
                StudyPlan,
                StudyPlanItem.plan_id == StudyPlan.plan_id,
            )
            .filter(
                StudyPlan.student_id == student_id,
                StudyPlan.status == "active",
                StudyPlanItem.status == "pending",
                StudyPlanItem.scheduled_date < datetime.combine(
                    today, time.min
                ),
            )
            .all()
        )

        updated_items = []

        for session in sessions:
            session.status = "overdue"
            updated_items.append(session.item_id)

        db.commit()

        print(
            f"[Session Lifecycle Agent] "
            f"Marked {len(updated_items)} session(s) overdue."
        )

        return {
            "success": True,
            "student_id": student_id,
            "updated_item_ids": updated_items,
            "count": len(updated_items),
        }

    except Exception as exc:
        db.rollback()
        print(
            f"[Session Lifecycle Agent] "
            f"Overdue detection failed: {exc}"
        )
        return {
            "success": False,
            "errors": [str(exc)],
        }

    finally:
        db.close()


def complete_session(student_id, item_id):
    """
    Mark a session completed only when it belongs to the
    specified student and their active study plan.

    Completed sessions cannot be reopened by this function.
    """
    db = SessionLocal()

    try:
        session = (
            db.query(StudyPlanItem)
            .join(
                StudyPlan,
                StudyPlanItem.plan_id == StudyPlan.plan_id,
            )
            .filter(
                StudyPlanItem.item_id == item_id,
                StudyPlan.student_id == student_id,
                StudyPlan.status == "active",
            )
            .first()
        )

        if session is None:
            return {
                "success": False,
                "errors": [
                    "Session not found in an active plan "
                    "for this student."
                ],
            }

        if session.status == "completed":
            return {
                "success": True,
                "item_id": session.item_id,
                "status": "completed",
                "message": "Session is already completed.",
            }

        if session.status not in {"pending", "overdue"}:
            return {
                "success": False,
                "errors": [
                    f"Cannot complete a session with "
                    f"status '{session.status}'."
                ],
            }

        session.status = "completed"
        db.commit()

        print(
            f"[Session Lifecycle Agent] "
            f"Session {item_id} marked completed."
        )

        return {
            "success": True,
            "item_id": session.item_id,
            "status": session.status,
            "message": "Session completed successfully.",
        }

    except Exception as exc:
        db.rollback()
        print(
            f"[Session Lifecycle Agent] "
            f"Completion failed: {exc}"
        )
        return {
            "success": False,
            "errors": [str(exc)],
        }

    finally:
        db.close()


def session_lifecycle_agent(state):
    """
    Dispatch lifecycle operations using workflow state.

    Supported actions:
      - detect_overdue
      - complete
    """
    action = state.get("session_action")
    student_id = state.get("student_id")

    if not student_id:
        return {
            "errors": ["Student ID is missing."],
            "next_action": "stop",
        }

    if action == "detect_overdue":
        result = detect_overdue_sessions(student_id)

    elif action == "complete":
        item_id = state.get("session_item_id")

        if not item_id:
            return {
                "errors": ["Session item ID is missing."],
                "next_action": "stop",
            }

        result = complete_session(student_id, item_id)

    else:
        return {
            "errors": [
                "Unsupported session action. "
                "Use 'detect_overdue' or 'complete'."
            ],
            "next_action": "stop",
        }

    return {
        "session_lifecycle_result": result,
        "next_action": (
            "complete" if result.get("success") else "stop"
        ),
    }
