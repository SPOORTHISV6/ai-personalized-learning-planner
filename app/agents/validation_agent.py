
from collections import defaultdict
from datetime import datetime


def validation_agent(state):
    print(
        "\n[Validation Agent] "
        "Validating study plan..."
    )

    plan = state.get("study_plan", {})
    profile = state.get("student_profile", {})
    sessions = plan.get("sessions", [])

    errors = []

    # -----------------------------------------
    # Validate available study time
    # -----------------------------------------

    try:
        daily_hours = float(
            profile.get("daily_available_hours", 0)
        )
    except (TypeError, ValueError):
        daily_hours = 0

    if daily_hours != daily_hours or daily_hours in (
        float("inf"),
        float("-inf"),
    ):
        daily_hours = 0

    daily_minutes = int(daily_hours * 60)

    if daily_minutes <= 0:
        errors.append(
            "Student has no available daily study time."
        )

    # -----------------------------------------
    # Validate sessions exist
    # -----------------------------------------

    if not sessions:
        errors.append(
            "Study plan contains no sessions."
        )

    # -----------------------------------------
    # Validate durations and group by date
    # -----------------------------------------

    daily_schedule = defaultdict(int)

    for session in sessions:
        session_date = session.get("date")
        duration = session.get("duration_minutes", 0)

        if not session_date:
            errors.append(
                "A study session is missing "
                "a scheduled date."
            )
            continue

        try:
            duration = int(duration)
        except (TypeError, ValueError):
            errors.append(
                f"Invalid duration for session on "
                f"{session_date}."
            )
            continue

        if duration <= 0:
            errors.append(
                f"Study session on {session_date} "
                "has invalid duration."
            )
            continue

        daily_schedule[session_date] += duration

    # -----------------------------------------
    # Validate daily time limits
    # -----------------------------------------

    for session_date, total_minutes in daily_schedule.items():
        print(
            "[Validation Agent] "
            f"{session_date}: "
            f"{total_minutes} / "
            f"{daily_minutes} minutes"
        )

        if total_minutes > daily_minutes:
            errors.append(
                f"Study plan exceeds "
                f"available study time on "
                f"{session_date}: "
                f"{total_minutes} minutes "
                f"scheduled, but only "
                f"{daily_minutes} minutes "
                f"are available."
            )

    # -----------------------------------------
    # Validate session dates strictly
    # -----------------------------------------

    for session in sessions:
        session_date = session.get("date")

        if not session_date:
            continue

        date_string = str(session_date)

        if "T" in date_string:
            errors.append(
                f"Session date {session_date} contains "
                "a timestamp. Expected YYYY-MM-DD."
            )
            continue

        try:
            parsed_date = datetime.strptime(
                date_string,
                "%Y-%m-%d",
            )

            # Enforce exact YYYY-MM-DD formatting.
            # strptime alone can accept some non-padded values.
            if parsed_date.strftime("%Y-%m-%d") != date_string:
                raise ValueError("Incorrect date format")

        except (ValueError, TypeError):
            errors.append(
                f"Invalid session date {session_date}. "
                "Expected a valid date in YYYY-MM-DD format."
            )

    # -----------------------------------------
    # Validate required session fields
    # -----------------------------------------

    for index, session in enumerate(sessions, start=1):
        required_fields = [
            "topic_id",
            "topic_name",
            "date",
            "duration_minutes",
            "priority",
        ]

        for field in required_fields:
            if session.get(field) is None:
                errors.append(
                    f"Session {index} is missing "
                    f"required field: {field}."
                )

    # -----------------------------------------
    # Return validation result
    # -----------------------------------------

    if errors:
        print(
            "[Validation Agent] "
            "Plan requires correction."
        )

        for error in errors:
            print(
                f"[Validation Agent] ERROR: {error}"
            )

        return {
            "validation": {
                "valid": False,
                "errors": errors,
            },
            "next_action": "replan",
        }

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
