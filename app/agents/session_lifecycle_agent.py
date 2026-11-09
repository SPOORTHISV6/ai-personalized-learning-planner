
import logging
from datetime import date, datetime, time

from app.database.connection import SessionLocal
from app.database.models import StudyPlan, StudyPlanItem


logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "overdue", "completed"}

SAFE_LIFECYCLE_ERROR = (
    "Session lifecycle operation could not be completed. "
    "Please try again later."
)


def _validate_positive_id(value):
    """
    Accept only positive integers or canonical positive integer strings.
    Reject booleans, floats, Decimal values, and malformed strings.
    """
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, str):
        if not value.isdigit():
            return None

        try:
            parsed_value = int(value)
        except (ValueError, OverflowError):
            return None

        if parsed_value <= 0 or str(parsed_value) != value:
            return None

        return parsed_value

    return None



def detect_overdue_sessions(student_id, today=None):
    """
    Mark pending sessions overdue when their scheduled date
    is earlier than today.

    Only active study plans are updated. Historical plans and
    completed sessions are left untouched.
    """

    student_id = _validate_positive_id(student_id)

    if student_id is None:
        return {
            "success": False,
            "errors": ["Student ID is invalid."],
        }

    today = today or date.today()

    if isinstance(today, datetime):
        today = today.date()

    if not isinstance(today, date):
        return {
            "success": False,
            "errors": ["The supplied date is invalid."],
        }

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
                    today,
                    time.min,
                ),
            )
            .all()
        )

        updated_items = []

        for session in sessions:
            session.status = "overdue"
            updated_items.append(session.item_id)

        db.commit()

        logger.info(
            "[Session Lifecycle Agent] Marked %s session(s) "
            "overdue for student_id=%s.",
            len(updated_items),
            student_id,
        )

        return {
            "success": True,
            "student_id": student_id,
            "updated_item_ids": updated_items,
            "count": len(updated_items),
        }

    except Exception:
        db.rollback()

        logger.exception(
            "[Session Lifecycle Agent] Overdue detection failed "
            "for student_id=%s.",
            student_id,
        )

        return {
            "success": False,
            "errors": [SAFE_LIFECYCLE_ERROR],
        }

    finally:
        db.close()


def complete_session(student_id, item_id):
    """
    Mark a session completed only when it belongs to the
    specified student and their active study plan.

    Completed sessions cannot be reopened by this function.
    """

    student_id = _validate_positive_id(student_id)
    item_id = _validate_positive_id(item_id)

    if student_id is None:
        return {
            "success": False,
            "errors": ["Student ID is invalid."],
        }

    if item_id is None:
        return {
            "success": False,
            "errors": ["Session item ID is invalid."],
        }

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

        logger.info(
            "[Session Lifecycle Agent] Session item_id=%s "
            "completed for student_id=%s.",
            item_id,
            student_id,
        )

        return {
            "success": True,
            "item_id": session.item_id,
            "status": session.status,
            "message": "Session completed successfully.",
        }

    except Exception:
        db.rollback()

        logger.exception(
            "[Session Lifecycle Agent] Completion failed "
            "for student_id=%s, item_id=%s.",
            student_id,
            item_id,
        )

        return {
            "success": False,
            "errors": [SAFE_LIFECYCLE_ERROR],
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

    if not isinstance(state, dict):
        return {
            "errors": ["Invalid workflow state."],
            "next_action": "stop",
        }

    action = state.get("session_action")
    student_id = _validate_positive_id(
        state.get("student_id")
    )

    if student_id is None:
        return {
            "errors": ["Student ID is missing or invalid."],
            "next_action": "stop",
        }

    if action == "detect_overdue":

        result = detect_overdue_sessions(student_id)

    elif action == "complete":

        item_id = _validate_positive_id(
            state.get("session_item_id")
        )

        if item_id is None:
            return {
                "errors": ["Session item ID is missing or invalid."],
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
