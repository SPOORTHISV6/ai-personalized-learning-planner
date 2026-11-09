from datetime import datetime, timedelta
import math
import re

from app.database.connection import SessionLocal
from app.database.models import Topic, Subject

from app.agents.performance_rules import (
    classify_performance,
    priority_for_level,
)


# ---------------------------------------------------------
# VALIDATION HELPERS
# ---------------------------------------------------------

def is_positive_integer(value):
    """Return True only for positive integers, excluding booleans."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def validate_score(value):
    """Validate and normalize a performance score in the range 0-100."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Performance score must be numeric.")

    score = float(value)

    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("Performance score must be between 0 and 100.")

    return score


def validate_topic_name(value, topic_id=None):
    """Sanitize and bound topic names before including them in a plan."""
    if value is None and is_positive_integer(topic_id):
        return f"Topic {topic_id}"

    if not isinstance(value, str):
        raise ValueError("Invalid topic name.")

    name = re.sub(r"[\x00-\x1f\x7f]", "", value).strip()
    name = name[:150]

    if not name:
        if is_positive_integer(topic_id):
            return f"Topic {topic_id}"

        raise ValueError("Topic name cannot be empty.")

    return name


def validate_daily_hours(value):
    """Accept finite numeric daily availability between 0 and 24 hours."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid daily available hours.")

    hours = float(value)

    if not math.isfinite(hours) or not 0 < hours <= 24:
        raise ValueError(
            "Daily available hours must be greater than 0 and at most 24."
        )

    return hours


def stop_workflow(message, student_id=None):
    """Return a safe terminal result for invalid workflow input."""
    safe_student_id = (
        student_id if is_positive_integer(student_id) else None
    )

    return {
        "study_plan": {
            "student_id": safe_student_id,
            "sessions": [],
            "total_sessions": 0,
        },
        "errors": [message],
        "next_action": "stop",
    }


# ---------------------------------------------------------
# TOPIC OWNERSHIP
# ---------------------------------------------------------

def get_owned_topic_ids(student_id):
    """
    Return topic IDs belonging to subjects owned by the given student.
    """
    if not is_positive_integer(student_id):
        raise ValueError("Invalid student ID.")

    db = SessionLocal()

    try:
        rows = (
            db.query(Topic.topic_id)
            .join(
                Subject,
                Topic.subject_id == Subject.subject_id,
            )
            .filter(
                Subject.student_id == student_id
            )
            .all()
        )

        return {
            row[0]
            for row in rows
            if is_positive_integer(row[0])
        }

    finally:
        db.close()


def filter_student_data(
    student_id,
    gaps,
    resources,
    student_memory,
    owned_topic_ids,
):
    """
    Remove foreign learning gaps, resources, performance records,
    and prerequisite references without mutating the caller's data.
    """

    if not is_positive_integer(student_id):
        raise ValueError("Invalid student ID.")

    if not isinstance(gaps, list) or any(
        not isinstance(item, dict) for item in gaps
    ):
        raise ValueError("Learning gaps must be a list of objects.")

    if not isinstance(resources, list) or any(
        not isinstance(item, dict) for item in resources
    ):
        raise ValueError("Resources must be a list of objects.")

    if not isinstance(student_memory, dict):
        raise ValueError("Student memory must be an object.")

    if not isinstance(owned_topic_ids, (set, list, tuple)):
        raise ValueError("Invalid owned-topic collection.")

    owned_topic_ids = {
        topic_id
        for topic_id in owned_topic_ids
        if is_positive_integer(topic_id)
    }

    # -----------------------------------------------------
    # FILTER LEARNING GAPS
    # -----------------------------------------------------

    valid_gaps = []

    for gap in gaps:
        topic_id = gap.get("topic_id")

        if not is_positive_integer(topic_id):
            raise ValueError("Invalid learning gap topic ID.")

        if topic_id not in owned_topic_ids:
            print(
                "[Study Plan Agent] "
                f"Rejected foreign learning gap: {topic_id}"
            )
            continue

        filtered_gap = dict(gap)

        prerequisite_id = filtered_gap.get(
            "prerequisite_topic_id"
        )

        if prerequisite_id is not None:

            if not is_positive_integer(prerequisite_id):
                raise ValueError("Invalid prerequisite topic ID.")

            if prerequisite_id == topic_id:
                raise ValueError(
                    "A topic cannot be its own prerequisite."
                )

            if prerequisite_id not in owned_topic_ids:
                print(
                    "[Study Plan Agent] "
                    f"Removed foreign prerequisite: {prerequisite_id}"
                )

                filtered_gap["prerequisite_topic_id"] = None

        valid_gaps.append(filtered_gap)

    # -----------------------------------------------------
    # FILTER RESOURCES
    # -----------------------------------------------------

    valid_resources = []

    for resource in resources:
        topic_id = resource.get("topic_id")

        if not is_positive_integer(topic_id):
            raise ValueError("Invalid resource topic ID.")

        if topic_id not in owned_topic_ids:
            print(
                "[Study Plan Agent] "
                f"Rejected foreign resource topic: {topic_id}"
            )
            continue

        valid_resources.append(dict(resource))

    # -----------------------------------------------------
    # FILTER STUDENT MEMORY
    # -----------------------------------------------------

    memory = dict(student_memory)

    latest_performance = memory.get(
        "latest_performance",
        [],
    )

    if not isinstance(latest_performance, list) or any(
        not isinstance(item, dict)
        for item in latest_performance
    ):
        raise ValueError("Invalid performance history.")

    valid_performance = []

    for performance in latest_performance:
        topic_id = performance.get("topic_id")

        if not is_positive_integer(topic_id):
            raise ValueError("Invalid performance topic ID.")

        if topic_id not in owned_topic_ids:
            print(
                "[Study Plan Agent] "
                f"Rejected foreign performance topic: {topic_id}"
            )
            continue

        valid_performance.append(dict(performance))

    memory["latest_performance"] = valid_performance

    return (
        valid_gaps,
        valid_resources,
        memory,
    )


# ---------------------------------------------------------
# PREREQUISITE CYCLE DETECTION
# ---------------------------------------------------------

def has_prerequisite_cycle(gaps):
    """
    Detect cycles in prerequisite relationships among supplied gaps.
    """

    prerequisite_map = {}

    for gap in gaps:
        topic_id = gap["topic_id"]

        prerequisite_id = gap.get(
            "prerequisite_topic_id"
        )

        if prerequisite_id is not None:
            prerequisite_map[topic_id] = prerequisite_id

    visiting = set()
    visited = set()

    def visit(topic_id):

        if topic_id in visiting:
            return True

        if topic_id in visited:
            return False

        visiting.add(topic_id)

        prerequisite_id = prerequisite_map.get(topic_id)

        if (
            prerequisite_id in prerequisite_map
            and visit(prerequisite_id)
        ):
            return True

        visiting.remove(topic_id)
        visited.add(topic_id)

        return False

    return any(
        visit(topic_id)
        for topic_id in prerequisite_map
        if topic_id not in visited
    )


# ---------------------------------------------------------
# RESOURCE HELPERS
# ---------------------------------------------------------

def get_resources_for_topic(resources, topic_id):
    """
    Return resources for a topic in the order provided by
    the Resource Agent.

    Do not sort by ranking score here. The Resource Agent has
    already selected and ordered resources for teaching.
    """

    topic_resources = []
    seen_sections = set()

    for resource in resources:

        if resource.get("topic_id") != topic_id:
            continue

        section_title = str(
            resource.get("section_title") or ""
        ).strip()

        # Avoid duplicate section titles without changing order.
        normalized_section = " ".join(
            section_title.lower().split()
        )

        if normalized_section:

            if normalized_section in seen_sections:
                continue

            seen_sections.add(normalized_section)

        topic_resources.append(resource)

    return topic_resources


def create_learning_objective(topic_name, resources):
    """
    Build an objective using every distinct section assigned
    to the session, preserving the Resource Agent's order.
    """

    if not resources:
        return (
            f"Study the fundamentals of {topic_name}."
        )

    sections = []
    seen_sections = set()

    for resource in resources:

        section = str(
            resource.get("section_title") or ""
        ).strip()

        if not section:
            continue

        normalized_section = " ".join(
            section.lower().split()
        )

        if normalized_section not in seen_sections:

            sections.append(section)
            seen_sections.add(normalized_section)

    if sections:

        section_names = ", ".join(sections)

        return (
            f"Study {topic_name} using the following "
            f"knowledge sections: {section_names}."
        )

    return (
        f"Study the fundamentals of {topic_name}."
    )


def build_resource_summary(resources):
    """
    Keep useful resource metadata inside the study plan.
    """

    resource_summary = []

    for resource in resources:

        resource_summary.append({
            "title": resource.get("title"),
            "source": resource.get("source"),
            "page_number": resource.get("page_number"),
            "section_title": resource.get("section_title"),
            "similarity_score": resource.get(
                "similarity_score"
            ),
            "ranking_score": resource.get(
                "ranking_score",
                resource.get("similarity_score", 0.0),
            ),
        })

    return resource_summary


# ---------------------------------------------------------
# STUDY ACTIVITY AND DURATION
# ---------------------------------------------------------

def create_study_activity(
    topic_name,
    score,
    priority,
    learning_preference,
    session_type="target_topic",
):
    """
    Generate an activity suited to the student's performance.
    """

    preference = (
        learning_preference or "General"
    ).lower()

    if session_type == "prerequisite_revision":

        if "practice" in preference:

            return (
                f"Revise the prerequisite concepts of {topic_name}, "
                "review examples, and solve a few practice questions "
                "before starting the dependent topic."
            )

        return (
            f"Review the prerequisite concepts required for "
            f"{topic_name}, with emphasis on the areas needed "
            "for the dependent topic."
        )

    if score < 50:

        if "practice" in preference:

            return (
                f"Revise {topic_name}, study the recommended material, "
                "work through examples, and complete practice questions."
            )

        return (
            f"Revise the fundamentals of {topic_name}, study the "
            "recommended material, and review examples."
        )

    if score < 75:

        if "practice" in preference:

            return (
                f"Review {topic_name}, study the recommended material, "
                "and solve targeted practice questions."
            )

        return (
            f"Review the important concepts of {topic_name} "
            "and reinforce them with examples."
        )

    return (
        f"Perform a short revision of {topic_name} "
        "and solve a few reinforcement questions."
    )


def calculate_duration(
    priority,
    score,
    daily_minutes,
    session_type="target_topic",
):
    """
    Calculate session duration within the daily time limit.
    """

    if daily_minutes <= 0:
        return 0

    if session_type == "prerequisite_revision":

        if score < 50:
            return min(daily_minutes, 40)

        if score < 75:
            return min(daily_minutes, 30)

        return min(daily_minutes, 20)

    if priority == "high":

        if score < 50:
            return min(daily_minutes, 60)

        return min(daily_minutes, 50)

    if priority == "medium":
        return min(daily_minutes, 45)

    return min(daily_minutes, 30)


# ---------------------------------------------------------
# STUDENT PERFORMANCE LOOKUP
# ---------------------------------------------------------

def build_topic_lookup(gaps, student_memory):
    """
    Build validated topic performance data.

    Priority and status are derived from the score using shared
    production rules. Incoming status and priority labels are
    not trusted.
    """

    if not isinstance(gaps, list) or any(
        not isinstance(item, dict)
        for item in gaps
    ):
        raise ValueError("Learning gaps must be a list of objects.")

    if not isinstance(student_memory, dict):
        raise ValueError("Student memory must be an object.")

    topic_lookup = {}

    # -----------------------------------------------------
    # LEARNING GAP RECORDS
    # -----------------------------------------------------

    for gap in gaps:

        topic_id = gap.get("topic_id")

        if not is_positive_integer(topic_id):
            raise ValueError("Invalid learning gap topic ID.")

        score = validate_score(
            gap.get("score", 0)
        )

        # Always derive classification from the actual score.
        status = classify_performance(score)
        priority = priority_for_level(status)

        prerequisite_id = gap.get(
            "prerequisite_topic_id"
        )

        if (
            prerequisite_id is not None
            and not is_positive_integer(prerequisite_id)
        ):
            raise ValueError("Invalid prerequisite topic ID.")

        topic_lookup[topic_id] = {
            "topic_id": topic_id,
            "topic_name": validate_topic_name(
                gap.get("topic_name"),
                topic_id,
            ),
            "score": score,
            "status": status,
            "priority": priority,
            "prerequisite_topic_id": prerequisite_id,
        }

    # -----------------------------------------------------
    # ADDITIONAL PERFORMANCE RECORDS FROM MEMORY
    # -----------------------------------------------------

    latest_performance = student_memory.get(
        "latest_performance",
        [],
    )

    if not isinstance(latest_performance, list) or any(
        not isinstance(item, dict)
        for item in latest_performance
    ):
        raise ValueError("Invalid performance history.")

    for performance in latest_performance:

        topic_id = performance.get("topic_id")

        if not is_positive_integer(topic_id):
            raise ValueError("Invalid performance topic ID.")

        if topic_id in topic_lookup:
            continue

        score = validate_score(
            performance.get("score", 0)
        )

        status = classify_performance(score)
        priority = priority_for_level(status)

        topic_lookup[topic_id] = {
            "topic_id": topic_id,
            "topic_name": validate_topic_name(
                performance.get("topic_name"),
                topic_id,
            ),
            "score": score,
            "status": status,
            "priority": priority,
            "prerequisite_topic_id": None,
        }

    return topic_lookup


def prerequisite_needs_revision(prerequisite):
    """
    A prerequisite scoring below 75 needs revision.
    """

    if not prerequisite:
        return False

    score = prerequisite.get("score")

    if score is None:
        return False

    return validate_score(score) < 75


# ---------------------------------------------------------
# SESSION BUILDERS
# ---------------------------------------------------------

def create_prerequisite_session(
    prerequisite,
    dependent_topic,
    date,
    daily_minutes,
    learning_preference,
    resources,
):
    """
    Create a revision session before a dependent topic.
    """

    prerequisite_id = prerequisite.get("topic_id")
    prerequisite_name = prerequisite.get("topic_name")

    prerequisite_score = validate_score(
        prerequisite.get("score", 0)
    )

    prerequisite_resources = get_resources_for_topic(
        resources,
        prerequisite_id,
    )

    duration = calculate_duration(
        priority=prerequisite.get(
            "priority",
            "medium",
        ),
        score=prerequisite_score,
        daily_minutes=daily_minutes,
        session_type="prerequisite_revision",
    )

    if prerequisite_score < 50:

        reason = (
            f"{prerequisite_name} is weak and is required "
            f"before {dependent_topic.get('topic_name')}."
        )

    else:

        reason = (
            f"{prerequisite_name} is not yet strong enough "
            f"for {dependent_topic.get('topic_name')}."
        )

    return {
        "topic_id": prerequisite_id,
        "topic_name": prerequisite_name,
        "date": date.isoformat(),
        "duration_minutes": duration,
        "priority": "high",
        "score": prerequisite_score,
        "learning_status": prerequisite.get("status"),
        "session_type": "prerequisite_revision",
        "reason": reason,
        "learning_objective": (
            f"Strengthen {prerequisite_name} before studying "
            f"{dependent_topic.get('topic_name')}."
        ),
        "study_activity": create_study_activity(
            topic_name=prerequisite_name,
            score=prerequisite_score,
            priority="high",
            learning_preference=learning_preference,
            session_type="prerequisite_revision",
        ),
        "resources": build_resource_summary(
            prerequisite_resources
        ),
        "expected_outcome": (
            f"Improve readiness for "
            f"{dependent_topic.get('topic_name')}."
        ),
    }


def create_target_session(
    topic,
    date,
    daily_minutes,
    learning_preference,
    resources,
):
    """
    Create the main personalized study session.
    """

    topic_id = topic.get("topic_id")
    topic_name = topic.get("topic_name")

    score = validate_score(
        topic.get("score", 0)
    )

    priority = topic.get(
        "priority",
        "medium",
    )

    # Preserve the exact order selected by the Resource Agent.
    topic_resources = get_resources_for_topic(
        resources,
        topic_id,
    )

    duration = calculate_duration(
        priority=priority,
        score=score,
        daily_minutes=daily_minutes,
        session_type="target_topic",
    )

    learning_objective = create_learning_objective(
        topic_name,
        topic_resources,
    )

    study_activity = create_study_activity(
        topic_name=topic_name,
        score=score,
        priority=priority,
        learning_preference=learning_preference,
        session_type="target_topic",
    )

    resource_summary = build_resource_summary(
        topic_resources
    )

    if score < 50:

        expected_outcome = (
            f"Improve understanding of {topic_name} "
            "and prepare for a follow-up assessment."
        )

    elif score < 75:

        expected_outcome = (
            f"Strengthen understanding of {topic_name} "
            "and improve problem-solving accuracy."
        )

    else:

        expected_outcome = (
            f"Maintain proficiency in {topic_name}."
        )

    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "date": date.isoformat(),
        "duration_minutes": duration,
        "priority": priority,
        "score": score,
        "learning_status": topic.get("status"),
        "session_type": "target_topic",
        "reason": (
            f"Targeted study based on {topic_name}'s current "
            f"performance score of {score}."
        ),
        "learning_objective": learning_objective,
        "study_activity": study_activity,
        "resources": resource_summary,
        "expected_outcome": expected_outcome,
    }


# ---------------------------------------------------------
# MAIN STUDY PLAN AGENT
# ---------------------------------------------------------

def study_plan_agent(state):
    """
    Generate a prerequisite-aware personalized study plan.

    The Resource Agent controls resource ordering.
    This agent preserves that order and includes every
    distinct selected section in the learning objective.

    Topic ownership is checked before generating sessions
    to prevent cross-student topic contamination.
    """

    print(
        "\n[Study Plan Agent] "
        "Generating prerequisite-aware study plan..."
    )

    # -----------------------------------------------------
    # 1. VALIDATE WORKFLOW STATE
    # -----------------------------------------------------

    if not isinstance(state, dict):
        return stop_workflow("Invalid workflow state.")

    profile = state.get(
        "student_profile",
        {},
    )

    gaps = state.get(
        "learning_gaps",
        [],
    )

    resources = state.get(
        "resources",
        [],
    )

    student_memory = state.get(
        "student_memory",
        {},
    )

    if not isinstance(profile, dict):
        return stop_workflow("Invalid student profile.")

    if not isinstance(gaps, list) or any(
        not isinstance(item, dict)
        for item in gaps
    ):
        return stop_workflow("Invalid learning gaps.")

    if not isinstance(resources, list) or any(
        not isinstance(item, dict)
        for item in resources
    ):
        return stop_workflow("Invalid learning resources.")

    if not isinstance(student_memory, dict):
        return stop_workflow("Invalid student memory.")

    # -----------------------------------------------------
    # 2. RESOLVE AND VALIDATE STUDENT ID
    # -----------------------------------------------------

    student_id = state.get("student_id")
    profile_student_id = profile.get("student_id")

    if student_id is None:
        student_id = profile_student_id

    if not is_positive_integer(student_id):
        return stop_workflow(
            "Invalid or missing student ID."
        )

    if profile_student_id is not None:

        if (
            not is_positive_integer(profile_student_id)
            or student_id != profile_student_id
        ):
            return stop_workflow(
                "Workflow student ID does not match student profile ID.",
                student_id,
            )

    # -----------------------------------------------------
    # 3. VALIDATE DAILY AVAILABILITY
    # -----------------------------------------------------

    try:

        daily_hours = validate_daily_hours(
            profile.get("daily_available_hours", 0)
        )

    except ValueError:

        return stop_workflow(
            "Invalid daily available study time.",
            student_id,
        )

    daily_minutes = int(
        daily_hours * 60
    )

    # -----------------------------------------------------
    # 4. VALIDATE LEARNING PREFERENCE
    # -----------------------------------------------------

    learning_preference = profile.get(
        "learning_preference",
        "General",
    )

    if not isinstance(learning_preference, str):
        learning_preference = "General"

    learning_preference = (
        re.sub(
            r"[\x00-\x1f\x7f]",
            "",
            learning_preference,
        )
        .strip()[:50]
        or "General"
    )

    # -----------------------------------------------------
    # 5. VERIFY TOPIC OWNERSHIP
    # -----------------------------------------------------

    try:

        owned_topic_ids = get_owned_topic_ids(
            student_id
        )

        if not isinstance(
            owned_topic_ids,
            (set, list, tuple),
        ):
            raise ValueError("Invalid ownership result.")

        owned_topic_ids = {
            topic_id
            for topic_id in owned_topic_ids
            if is_positive_integer(topic_id)
        }

    except Exception:

        print(
            "[Study Plan Agent] "
            "Topic ownership verification failed."
        )

        return stop_workflow(
            "Could not verify topic ownership.",
            student_id,
        )

    print(
        "[Study Plan Agent] "
        f"Owned topics found: {len(owned_topic_ids)}"
    )

    # -----------------------------------------------------
    # 6. FILTER AND VALIDATE STUDENT DATA
    # -----------------------------------------------------

    try:

        (
            gaps,
            resources,
            student_memory,
        ) = filter_student_data(
            student_id=student_id,
            gaps=gaps,
            resources=resources,
            student_memory=student_memory,
            owned_topic_ids=owned_topic_ids,
        )

        topic_lookup = build_topic_lookup(
            gaps,
            student_memory,
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
    ):

        return stop_workflow(
            "Invalid learning data received by the Study Plan Agent.",
            student_id,
        )

    # -----------------------------------------------------
    # 7. CHECK PREREQUISITE CYCLES
    # -----------------------------------------------------

    if has_prerequisite_cycle(gaps):

        return stop_workflow(
            "Circular prerequisite relationship detected.",
            student_id,
        )

    print(
        "[Study Plan Agent] "
        f"Valid learning gaps: {len(gaps)}"
    )

    # -----------------------------------------------------
    # 8. SELECT HIGH- AND MEDIUM-PRIORITY TOPICS
    # -----------------------------------------------------

    # Never trust the incoming priority/status fields.
    # Classification is derived from validated performance scores.

    high_priority = [
        gap
        for gap in gaps
        if topic_lookup[gap["topic_id"]]["priority"] == "high"
    ]

    medium_priority = [
        gap
        for gap in gaps
        if topic_lookup[gap["topic_id"]]["priority"] == "medium"
    ]

    selected_topics = (
        high_priority + medium_priority
    )

    if not selected_topics:

        print(
            "[Study Plan Agent] "
            "No significant learning gaps found."
        )

        return {
            "study_plan": {
                "student_id": student_id,
                "daily_available_hours": daily_hours,
                "learning_preference": learning_preference,
                "sessions": [],
                "total_sessions": 0,
                "planning_strategy": "prerequisite_aware",
            },
            "next_action": "validation",
        }

    # -----------------------------------------------------
    # 9. GENERATE STUDY SESSIONS
    # -----------------------------------------------------

    sessions = []

    scheduled_topic_ids = set()

    current_date = datetime.now().date()

    for gap in selected_topics:

        topic_id = gap["topic_id"]

        # Defensive ownership check before scheduling.
        if topic_id not in owned_topic_ids:

            print(
                "[Study Plan Agent] "
                f"Skipping unowned target topic: {topic_id}"
            )

            continue

        if topic_id in scheduled_topic_ids:
            continue

        topic = topic_lookup[topic_id]

        # -------------------------------------------------
        # 10. CHECK PREREQUISITE
        # -------------------------------------------------

        prerequisite_id = topic.get(
            "prerequisite_topic_id"
        )

        prerequisite = (
            topic_lookup.get(prerequisite_id)
            if prerequisite_id is not None
            else None
        )

        if prerequisite is not None:

            if prerequisite_needs_revision(prerequisite):

                prerequisite_id = prerequisite.get(
                    "topic_id"
                )

                # Ensure prerequisite belongs to this student.
                if prerequisite_id not in owned_topic_ids:

                    print(
                        "[Study Plan Agent] "
                        f"Skipping foreign prerequisite: "
                        f"{prerequisite_id}"
                    )

                elif prerequisite_id not in scheduled_topic_ids:

                    prerequisite_date = (
                        current_date
                        + timedelta(days=len(sessions))
                    )

                    prerequisite_session = (
                        create_prerequisite_session(
                            prerequisite=prerequisite,
                            dependent_topic=topic,
                            date=prerequisite_date,
                            daily_minutes=daily_minutes,
                            learning_preference=learning_preference,
                            resources=resources,
                        )
                    )

                    sessions.append(
                        prerequisite_session
                    )

                    scheduled_topic_ids.add(
                        prerequisite_id
                    )

                    print(
                        "[Study Plan Agent] "
                        "Prerequisite session: "
                        f"{prerequisite.get('topic_name')} "
                        f"before {topic.get('topic_name')}"
                    )

            else:

                print(
                    "[Study Plan Agent] "
                    "Prerequisite satisfied: "
                    f"{prerequisite.get('topic_name')} "
                    f"score = {prerequisite.get('score')}"
                )

        # -------------------------------------------------
        # 11. CREATE TARGET SESSION
        # -------------------------------------------------

        target_date = (
            current_date
            + timedelta(days=len(sessions))
        )

        target_session = create_target_session(
            topic=topic,
            date=target_date,
            daily_minutes=daily_minutes,
            learning_preference=learning_preference,
            resources=resources,
        )

        sessions.append(
            target_session
        )

        scheduled_topic_ids.add(
            topic_id
        )

        print(
            "[Study Plan Agent] Target session: "
            f"{topic.get('topic_name')} | "
            f"{target_session['duration_minutes']} min | "
            f"{topic.get('priority')}"
        )

        print(
            "[Study Plan Agent] Learning objective: "
            f"{target_session['learning_objective']}"
        )

        print(
            "[Study Plan Agent] Resource sections: "
            + ", ".join(
                item.get("section_title") or "Untitled"
                for item in target_session["resources"]
            )
        )

    # -----------------------------------------------------
    # 12. BUILD FINAL STUDY PLAN
    # -----------------------------------------------------

    study_plan = {
        "student_id": student_id,
        "daily_available_hours": daily_hours,
        "learning_preference": learning_preference,
        "total_sessions": len(sessions),
        "planning_strategy": "prerequisite_aware",
        "sessions": sessions,
    }

    print(
        "[Study Plan Agent] "
        f"Created {len(sessions)} prerequisite-aware sessions."
    )

    return {
        "study_plan": study_plan,
        "next_action": "validation",
    }