import logging
import math
import re
from collections import defaultdict
from datetime import datetime

from app.database.connection import SessionLocal
from app.database.models import Topic, Subject


logger = logging.getLogger(__name__)

MAX_DAILY_HOURS = 24
MAX_TOPIC_NAME_LENGTH = 150
ALLOWED_PRIORITIES = {"high", "medium", "low"}


# =========================================================
# VALIDATION HELPERS
# =========================================================

def _parse_positive_id(value):
    """
    Accept positive integers only.
    Explicitly reject booleans and numeric strings.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int) and value > 0:
        return value

    return None


def _parse_duration(value):
    """
    Return a positive whole-number duration, or None if invalid.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, float):

        if (
            math.isfinite(value)
            and value.is_integer()
            and value > 0
        ):
            return int(value)

        return None

    if isinstance(value, str):

        if re.fullmatch(r"[1-9]\d*", value):
            return int(value)

    return None


def _validate_daily_hours(value):
    """
    Validate daily available study hours.

    Accepted range: greater than 0 and at most 24.
    """

    if isinstance(value, bool):
        return None

    if not isinstance(value, (int, float)):
        return None

    hours = float(value)

    if not math.isfinite(hours):
        return None

    if not 0 < hours <= MAX_DAILY_HOURS:
        return None

    return hours


def _validate_topic_name(value):
    """
    Validate topic names and reject empty or non-string values.
    """

    if not isinstance(value, str):
        return False

    cleaned = re.sub(
        r"[\x00-\x1f\x7f]",
        "",
        value,
    ).strip()

    if not cleaned:
        return False

    if len(cleaned) > MAX_TOPIC_NAME_LENGTH:
        return False

    return True


def _validate_priority(value):
    """
    Accept only supported priority levels.
    """

    if not isinstance(value, str):
        return False

    return value.strip().lower() in ALLOWED_PRIORITIES


def _validate_session_date(value):
    """
    Validate strict YYYY-MM-DD calendar dates.

    Historical dates remain accepted for compatibility
    with existing study-plan records.
    """

    if not isinstance(value, str):
        return False

    if "T" in value:
        return False

    try:
        parsed_date = datetime.strptime(
            value,
            "%Y-%m-%d",
        )

        return parsed_date.strftime("%Y-%m-%d") == value

    except (ValueError, TypeError, OverflowError):
        return False


# =========================================================
# TOPIC OWNERSHIP
# =========================================================

def get_owned_topic_ids(student_id, topic_ids):
    """
    Fetch topic IDs belonging to subjects owned by the
    specified student.
    """

    student_id = _parse_positive_id(student_id)

    if student_id is None:
        return set()

    if not isinstance(topic_ids, (list, tuple, set)):
        return set()

    topic_ids = {
        parsed_id
        for value in topic_ids
        if (
            parsed_id := _parse_positive_id(value)
        ) is not None
    }

    if not topic_ids:
        return set()

    db = SessionLocal()

    try:

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

        return {
            row[0]
            for row in rows
            if _parse_positive_id(row[0]) is not None
        }

    finally:
        db.close()


# =========================================================
# ERROR RESULT
# =========================================================

def _invalid_result(errors):
    """
    Return a standard validation failure result.
    """

    for error in errors:
        logger.warning(
            "[Validation Agent] %s",
            error,
        )

    return {
        "validation": {
            "valid": False,
            "errors": errors,
        },
        "next_action": "replan",
    }


# =========================================================
# MAIN VALIDATION AGENT
# =========================================================

def validation_agent(state):

    print(
        "\n[Validation Agent] "
        "Validating study plan..."
    )

    errors = []

    # -----------------------------------------------------
    # 1. VALIDATE WORKFLOW STATE
    # -----------------------------------------------------

    if not isinstance(state, dict):

        return _invalid_result([
            "Workflow state must be a dictionary."
        ])

    plan = state.get("study_plan")
    profile = state.get("student_profile")

    if not isinstance(plan, dict):

        errors.append(
            "Study plan is missing or invalid."
        )

        plan = {}

    if not isinstance(profile, dict):

        errors.append(
            "Student profile is missing or invalid."
        )

        profile = {}

    sessions = plan.get("sessions", [])

    if not isinstance(sessions, list):

        errors.append(
            "Study plan sessions must be a list."
        )

        sessions = []

    # -----------------------------------------------------
    # 2. VALIDATE STUDENT ID
    # -----------------------------------------------------

    raw_student_id = state.get("student_id")
    profile_student_id = profile.get("student_id")

    if raw_student_id is None:
        raw_student_id = profile_student_id

    student_id = _parse_positive_id(
        raw_student_id
    )

    if student_id is None:

        errors.append(
            "Student ID is missing or invalid in workflow state."
        )

    # When both IDs are supplied, require exact integer equality.
    if (
        state.get("student_id") is not None
        and profile_student_id is not None
    ):

        if (
            student_id is None
            or _parse_positive_id(profile_student_id) is None
            or student_id != profile_student_id
        ):

            errors.append(
                "Workflow student ID does not match "
                "the student profile ID."
            )

    # -----------------------------------------------------
    # 3. VALIDATE DAILY AVAILABLE STUDY TIME
    # -----------------------------------------------------

    daily_hours = _validate_daily_hours(
        profile.get("daily_available_hours", 0)
    )

    if daily_hours is None:

        daily_minutes = 0

        errors.append(
            "Student has no available daily study time."
        )

        errors.append(
            "Daily available hours must be a valid number "
            "greater than 0 and at most 24."
        )

    else:

        daily_minutes = int(
            daily_hours * 60
        )

    # -----------------------------------------------------
    # 4. VERIFY STUDY PLAN OWNER
    # -----------------------------------------------------

    raw_plan_student_id = plan.get("student_id")

    plan_student_id = _parse_positive_id(
        raw_plan_student_id
    )

    if plan_student_id is None:

        errors.append(
            "Study plan student ID is missing or invalid."
        )

    elif (
        student_id is not None
        and plan_student_id != student_id
    ):

        errors.append(
            "Study plan student ID does not match "
            "the current workflow student."
        )

    # -----------------------------------------------------
    # 5. VALIDATE SESSION EXISTENCE
    # -----------------------------------------------------

    if not sessions:

        errors.append(
            "Study plan contains no sessions."
        )

    # -----------------------------------------------------
    # 6. VALIDATE TOTAL SESSION COUNT
    # -----------------------------------------------------

    if "total_sessions" in plan:

        declared_total = plan.get("total_sessions")

        if (
            isinstance(declared_total, bool)
            or not isinstance(declared_total, int)
            or declared_total != len(sessions)
        ):

            errors.append(
                "Study plan total_sessions does not match "
                "the actual number of sessions."
            )

    # -----------------------------------------------------
    # 7. VALIDATE SESSION STRUCTURE
    # -----------------------------------------------------

    required_fields = [
        "topic_id",
        "topic_name",
        "date",
        "duration_minutes",
        "priority",
    ]

    topic_ids = set()
    seen_topic_ids = set()
    valid_sessions = []

    for index, session in enumerate(
        sessions,
        start=1,
    ):

        if not isinstance(session, dict):

            errors.append(
                f"Session {index} must be a dictionary."
            )

            continue

        valid_sessions.append(session)

        # ---------------------------------------------
        # Required fields
        # ---------------------------------------------

        for field in required_fields:

            if session.get(field) is None:

                errors.append(
                    f"Session {index} is missing "
                    f"required field: {field}."
                )

                if field == "date":

                    errors.append(
                        "A study session is missing "
                        "a scheduled date."
                    )

        # ---------------------------------------------
        # Topic ID
        # ---------------------------------------------

        raw_topic_id = session.get("topic_id")

        if raw_topic_id is not None:

            topic_id = _parse_positive_id(
                raw_topic_id
            )

            if topic_id is None:

                errors.append(
                    f"Session {index} has an invalid topic ID."
                )

            else:

                topic_ids.add(topic_id)

                if topic_id in seen_topic_ids:

                    errors.append(
                        f"Duplicate topic ID {topic_id} "
                        "appears in the study plan."
                    )

                else:

                    seen_topic_ids.add(topic_id)

        # ---------------------------------------------
        # Topic name
        # ---------------------------------------------

        topic_name = session.get("topic_name")

        if topic_name is not None:

            if not _validate_topic_name(topic_name):

                errors.append(
                    f"Session {index} has an invalid topic name."
                )

        # ---------------------------------------------
        # Priority
        # ---------------------------------------------

        priority = session.get("priority")

        if priority is not None:

            if not _validate_priority(priority):

                errors.append(
                    f"Session {index} has an invalid priority. "
                    "Allowed values are high, medium, and low."
                )

    # -----------------------------------------------------
    # 8. VERIFY TOPIC OWNERSHIP
    # -----------------------------------------------------

    if student_id is not None and topic_ids:

        try:

            owned_topic_ids = get_owned_topic_ids(
                student_id,
                topic_ids,
            )

            if not isinstance(
                owned_topic_ids,
                (set, list, tuple),
            ):

                raise ValueError(
                    "Invalid ownership verification result."
                )

            owned_topic_ids = {
                topic_id
                for value in owned_topic_ids
                if (
                    topic_id := _parse_positive_id(value)
                ) is not None
            }

            invalid_topic_ids = (
                topic_ids - owned_topic_ids
            )

            for invalid_id in sorted(invalid_topic_ids):

                errors.append(
                    f"Topic ID {invalid_id} does not "
                    f"belong to student {student_id}."
                )

        except Exception:

            # Never log raw database exception messages or tracebacks.
            logger.warning(
                "[Validation Agent] "
                "Topic ownership verification failed."
            )

            errors.append(
                "Could not verify topic ownership. "
                "Please try again later."
            )

    # -----------------------------------------------------
    # 9. VALIDATE SESSION DURATIONS AND DAILY SCHEDULE
    # -----------------------------------------------------

    daily_schedule = defaultdict(int)

    for index, session in enumerate(
        valid_sessions,
        start=1,
    ):

        session_date = session.get("date")

        if not session_date:
            continue

        duration = _parse_duration(
            session.get("duration_minutes")
        )

        if duration is None:

            errors.append(
                f"Invalid duration for session {index}."
            )

            continue

        # Only aggregate durations for valid dates.
        if not _validate_session_date(session_date):
            continue

        daily_schedule[session_date] += duration

    # -----------------------------------------------------
    # 10. VALIDATE DAILY TIME LIMITS
    # -----------------------------------------------------

    if daily_minutes > 0:

        for session_date, total_minutes in daily_schedule.items():

            print(
                "[Validation Agent] "
                f"{session_date}: "
                f"{total_minutes} / {daily_minutes} minutes"
            )

            if total_minutes > daily_minutes:

                errors.append(
                    "Study plan exceeds available study time "
                    f"on {session_date}: {total_minutes} minutes "
                    f"scheduled, but only {daily_minutes} "
                    "minutes are available."
                )

    # -----------------------------------------------------
    # 11. VALIDATE SESSION DATE FORMAT
    # -----------------------------------------------------

    for index, session in enumerate(
        valid_sessions,
        start=1,
    ):

        session_date = session.get("date")

        if not session_date:
            continue

        if not isinstance(session_date, str):

            errors.append(
                f"Invalid session date {session_date}. "
                "Expected a valid date in YYYY-MM-DD format."
            )

            continue

        if "T" in session_date:

            errors.append(
                f"Session date {session_date} contains "
                "a timestamp. Expected YYYY-MM-DD."
            )

            continue

        if not _validate_session_date(session_date):

            errors.append(
                f"Invalid session date {session_date}. "
                "Expected a valid date in YYYY-MM-DD format."
            )

    # -----------------------------------------------------
    # 12. RETURN VALIDATION RESULT
    # -----------------------------------------------------

    if errors:

        print(
            "[Validation Agent] "
            "Plan requires correction."
        )

        return _invalid_result(errors)

    print(
        "[Validation Agent] "
        "Study plan is valid."
    )

    return {
        "validation": {
            "valid": True,
            "errors": [],
        },
        "next_action": "complete",
    }