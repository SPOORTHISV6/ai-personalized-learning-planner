
import logging
from datetime import date, datetime

from app.database.connection import SessionLocal
from app.database.models import (
    StudyPlan,
    StudyPlanItem,
    Topic,
    Subject,
)


logger = logging.getLogger(__name__)

SAFE_PERSISTENCE_ERROR = (
    "Study plan persistence could not be completed. "
    "Please try again later."
)

PRIORITY_MAP = {
    "high": 5,
    "medium": 3,
    "low": 1,
}

VALID_DATABASE_PRIORITIES = {1, 3, 5}


# ---------------------------------------------------------
# STRICT VALIDATION HELPERS
# ---------------------------------------------------------

def is_positive_integer(value):
    """Accept positive integer values, but reject bool and strings."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def normalize_session_date(value):
    """Validate and normalize a session date to YYYY-MM-DD."""
    if isinstance(value, datetime):
        raise ValueError("Datetime values are not accepted as dates.")

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise ValueError("Session date must be an ISO date string.")

    if len(value) != 10:
        raise ValueError("Session date must use YYYY-MM-DD format.")

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid calendar date.") from exc

    if parsed.isoformat() != value:
        raise ValueError("Session date must use YYYY-MM-DD format.")

    return parsed


def normalize_duration(value):
    """Accept positive integer minute durations only."""
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise ValueError("Duration must be a positive integer.")

    return value


def normalize_priority(value):
    """Convert supported priority labels to database integers."""
    if isinstance(value, bool):
        raise ValueError("Boolean priority is invalid.")

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized not in PRIORITY_MAP:
            raise ValueError("Unsupported priority.")

        return PRIORITY_MAP[normalized]

    if (
        isinstance(value, int)
        and value in VALID_DATABASE_PRIORITIES
    ):
        return value

    raise ValueError("Unsupported priority.")


def error_result(message):
    """Return a consistent workflow stop result."""
    return {
        "errors": [message],
        "next_action": "stop",
    }


# ---------------------------------------------------------
# TOPIC OWNERSHIP
# ---------------------------------------------------------

def get_owned_topic_ids(db, student_id, topic_ids):
    """
    Return topic IDs belonging to subjects owned by the student.
    """
    topic_ids = set(topic_ids or [])

    if not topic_ids:
        return set()

    rows = (
        db.query(Topic.topic_id)
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(
            Subject.student_id == student_id,
            Topic.topic_id.in_(topic_ids),
        )
        .all()
    )

    return {row[0] for row in rows}


# ---------------------------------------------------------
# MAIN PERSISTENCE AGENT
# ---------------------------------------------------------

def persistence_agent(state):
    """
    Persist a validated adaptive study plan.

    Guarantees:
    - Strict input validation before opening a DB session.
    - Student and topic ownership verification.
    - Identical active-plan reuse.
    - Existing active-plan superseding.
    - Atomic database transaction.
    - Rollback on persistence failures.
    """

    logger.info(
        "[Persistence Agent] Persisting adaptive study plan."
    )

    # -----------------------------------------------------
    # 1. VALIDATE WORKFLOW STATE
    # -----------------------------------------------------

    if not isinstance(state, dict):
        return error_result("Invalid workflow state.")

    student_id = state.get("student_id")
    study_plan = state.get("study_plan")
    validation = state.get("validation")

    if student_id is None:
        return error_result("Student ID is missing.")

    if not is_positive_integer(student_id):
        return error_result("Student ID is invalid.")

    if not isinstance(study_plan, dict):
        return error_result("Study plan has an invalid format.")

    if not isinstance(validation, dict):
        return error_result("Study plan validation result is invalid.")

    if validation.get("valid") is not True:
        return error_result("Study plan validation failed.")

    # -----------------------------------------------------
    # 2. VERIFY PLAN OWNERSHIP
    # -----------------------------------------------------

    plan_student_id = study_plan.get("student_id")

    if not is_positive_integer(plan_student_id):
        return error_result(
            "Study plan contains a missing or invalid student ID."
        )

    if plan_student_id != student_id:
        return error_result(
            "Study plan student ID does not match "
            "the current workflow student."
        )

    # -----------------------------------------------------
    # 3. VALIDATE ALL SESSIONS BEFORE DATABASE ACCESS
    # -----------------------------------------------------

    sessions = study_plan.get("sessions")

    if not isinstance(sessions, list) or not sessions:
        return error_result(
            "Study plan contains no valid sessions."
        )

    prepared_sessions = []
    topic_ids = []
    session_dates = []

    for index, session in enumerate(sessions, start=1):

        if not isinstance(session, dict):
            return error_result(
                f"Session {index} has an invalid format."
            )

        topic_id = session.get("topic_id")

        if not is_positive_integer(topic_id):
            return error_result(
                f"Session {index} has an invalid topic_id."
            )

        try:
            session_date = normalize_session_date(
                session.get("date")
            )
        except (TypeError, ValueError):
            return error_result(
                f"Session {index} has an invalid date."
            )

        try:
            duration = normalize_duration(
                session.get("duration_minutes")
            )
        except (TypeError, ValueError):
            return error_result(
                f"Session {index} has an invalid duration."
            )

        try:
            priority = normalize_priority(
                session.get("priority", "medium")
            )
        except (TypeError, ValueError):
            return error_result(
                f"Session {index} has an invalid priority."
            )

        prepared_session = {
            **session,
            "topic_id": topic_id,
            "date": session_date,
            "duration_minutes": duration,
            "priority": priority,
        }

        prepared_sessions.append(prepared_session)
        topic_ids.append(topic_id)
        session_dates.append(session_date)

    # All input validation is complete before DB session creation.
    start_date = min(session_dates)
    end_date = max(session_dates)

    # -----------------------------------------------------
    # 4. OPEN DATABASE SESSION
    # -----------------------------------------------------

    db = None

    try:
        db = SessionLocal()

        # -------------------------------------------------
        # 5. VERIFY TOPIC OWNERSHIP
        # -------------------------------------------------

        owned_topic_ids = get_owned_topic_ids(
            db,
            student_id,
            topic_ids,
        )

        requested_topic_ids = set(topic_ids)

        invalid_topic_ids = (
            requested_topic_ids - owned_topic_ids
        )

        if invalid_topic_ids:
            logger.warning(
                "[Persistence Agent] Rejected foreign or "
                "invalid topic IDs for student_id=%s: %s",
                student_id,
                sorted(invalid_topic_ids),
            )

            return error_result(
                "Study plan contains topic IDs that do not "
                "belong to the current student."
            )

        # -------------------------------------------------
        # 6. FETCH ACTIVE PLANS FOR THIS STUDENT
        # -------------------------------------------------

        active_plans = (
            db.query(StudyPlan)
            .filter(
                StudyPlan.student_id == student_id,
                StudyPlan.status == "active",
            )
            .all()
        )

        # -------------------------------------------------
        # 7. CHECK FOR AN IDENTICAL ACTIVE PLAN
        # -------------------------------------------------

        identical_plan = None

        for existing_plan in active_plans:

            existing_items = (
                db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.plan_id == existing_plan.plan_id
                )
                .order_by(
                    StudyPlanItem.scheduled_date
                )
                .all()
            )

            if len(existing_items) != len(prepared_sessions):
                continue

            # Defense in depth: reject reuse of corrupted plans
            # containing topics owned by another student.

            existing_topic_ids = {
                item.topic_id for item in existing_items
            }

            existing_owned_ids = get_owned_topic_ids(
                db,
                student_id,
                existing_topic_ids,
            )

            if existing_topic_ids != existing_owned_ids:
                logger.warning(
                    "[Persistence Agent] Skipping corrupted "
                    "active plan_id=%s for student_id=%s.",
                    existing_plan.plan_id,
                    student_id,
                )
                continue

            plan_matches = True

            for existing_item, session in zip(
                existing_items,
                prepared_sessions,
            ):

                existing_date = existing_item.scheduled_date

                if isinstance(existing_date, datetime):
                    existing_date = existing_date.date()

                if isinstance(existing_date, str):
                    try:
                        existing_date = date.fromisoformat(
                            existing_date[:10]
                        )
                    except ValueError:
                        plan_matches = False
                        break

                if (
                    existing_item.topic_id != session["topic_id"]
                    or existing_date != session["date"]
                    or existing_item.duration_minutes
                    != session["duration_minutes"]
                    or existing_item.priority != session["priority"]
                ):
                    plan_matches = False
                    break

            if plan_matches:
                identical_plan = existing_plan
                break

        # -------------------------------------------------
        # 8. REUSE IDENTICAL ACTIVE PLAN
        # -------------------------------------------------

        if identical_plan:

            logger.info(
                "[Persistence Agent] Reusing identical active plan."
            )

            existing_items = (
                db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.plan_id
                    == identical_plan.plan_id
                )
                .order_by(
                    StudyPlanItem.scheduled_date
                )
                .all()
            )

            persisted_items = []

            for item in existing_items:
                persisted_items.append({
                    "item_id": item.item_id,
                    "topic_id": item.topic_id,
                    "scheduled_date": str(
                        item.scheduled_date
                    )[:10],
                    "duration_minutes": item.duration_minutes,
                    "priority": item.priority,
                    "status": item.status,
                })

            return {
                "persisted_plan": {
                    "plan_id": identical_plan.plan_id,
                    "student_id": identical_plan.student_id,
                    "start_date": str(
                        identical_plan.start_date
                    ),
                    "end_date": str(
                        identical_plan.end_date
                    ),
                    "status": identical_plan.status,
                    "total_sessions": len(persisted_items),
                    "created_new_plan": False,
                    "items": persisted_items,
                },
                "persistence_action": "reused",
                "next_action": "complete",
            }

        # -------------------------------------------------
        # 9. CREATE A NEW PLAN
        # -------------------------------------------------

        logger.info(
            "[Persistence Agent] New adaptive plan detected."
        )

        # Supersede previous active plans only after all
        # incoming sessions pass validation and ownership checks.

        for old_plan in active_plans:
            old_plan.status = "superseded"

        db.flush()

        logger.info(
            "[Persistence Agent] Superseded %s previous "
            "active plan(s) for student_id=%s.",
            len(active_plans),
            student_id,
        )

        new_plan = StudyPlan(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            status="active",
        )

        db.add(new_plan)
        db.flush()

        # -------------------------------------------------
        # 10. CREATE STUDY PLAN ITEMS
        # -------------------------------------------------

        persisted_items = []

        for session in prepared_sessions:

            item = StudyPlanItem(
                plan_id=new_plan.plan_id,
                topic_id=session["topic_id"],
                scheduled_date=session["date"],
                duration_minutes=session["duration_minutes"],
                priority=session["priority"],
                status="pending",
            )

            db.add(item)
            db.flush()

            persisted_items.append({
                "item_id": item.item_id,
                "topic_id": item.topic_id,
                "scheduled_date": str(
                    item.scheduled_date
                )[:10],
                "duration_minutes": item.duration_minutes,
                "priority": item.priority,
                "status": item.status,
            })

        # -------------------------------------------------
        # 11. COMMIT TRANSACTION
        # -------------------------------------------------

        db.commit()
        db.refresh(new_plan)

        logger.info(
            "[Persistence Agent] Created new StudyPlan ID: %s",
            new_plan.plan_id,
        )

        return {
            "persisted_plan": {
                "plan_id": new_plan.plan_id,
                "student_id": new_plan.student_id,
                "start_date": str(new_plan.start_date),
                "end_date": str(new_plan.end_date),
                "status": new_plan.status,
                "total_sessions": len(persisted_items),
                "created_new_plan": True,
                "items": persisted_items,
            },
            "persistence_action": "created_new_plan",
            "next_action": "complete",
        }

    # -----------------------------------------------------
    # 12. ERROR HANDLING AND ROLLBACK
    # -----------------------------------------------------

    except Exception:
        if db is not None:
            db.rollback()

        logger.exception(
            "[Persistence Agent] Unexpected persistence error "
            "for student_id=%s.",
            student_id,
        )

        return {
            "errors": [SAFE_PERSISTENCE_ERROR],
            "next_action": "stop",
        }

    # -----------------------------------------------------
    # 13. CLOSE DATABASE SESSION
    # -----------------------------------------------------

    finally:
        if db is not None:
            db.close()
