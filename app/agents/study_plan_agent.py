
from datetime import datetime, timedelta

from app.agents.performance_rules import (
    classify_performance,
    priority_for_level,
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
        return f"Study the fundamentals of {topic_name}."

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

    return f"Study the fundamentals of {topic_name}."


def build_resource_summary(resources):
    """Keep useful resource metadata inside the study plan."""
    resource_summary = []

    for resource in resources:
        resource_summary.append({
            "title": resource.get("title"),
            "source": resource.get("source"),
            "page_number": resource.get("page_number"),
            "section_title": resource.get("section_title"),
            "similarity_score": resource.get("similarity_score"),
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
    """Generate an activity suited to the student's performance."""

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
    """Calculate session duration within the daily time limit."""

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
    Build a lookup of topics using learning gaps and any
    additional latest-performance records in student memory.
    """
    topic_lookup = {}

    for gap in gaps:
        topic_id = gap.get("topic_id")

        if topic_id is None:
            continue

        topic_lookup[topic_id] = {
            "topic_id": topic_id,
            "topic_name": gap.get("topic_name"),
            "score": float(gap.get("score", 0)),
            "status": gap.get("status"),
            "priority": gap.get("priority", "low"),
            "prerequisite_topic_id": gap.get(
                "prerequisite_topic_id"
            ),
        }

    memory = student_memory or {}

    for performance in memory.get("latest_performance", []):
        topic_id = performance.get("topic_id")

        if topic_id is None or topic_id in topic_lookup:
            continue

        score = float(performance.get("score", 0))

        # Use the same production rules as the Evaluation Agent.
        status = classify_performance(score)
        priority = priority_for_level(status)

        topic_lookup[topic_id] = {
            "topic_id": topic_id,
            "topic_name": performance.get("topic_name"),
            "score": score,
            "status": status,
            "priority": priority,
            "prerequisite_topic_id": None,
        }

    return topic_lookup


def prerequisite_needs_revision(prerequisite):
    """A prerequisite scoring below 75 needs revision."""
    if not prerequisite:
        return False

    score = prerequisite.get("score")

    if score is None:
        return False

    return float(score) < 75


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
    """Create a revision session before a dependent topic."""

    prerequisite_id = prerequisite.get("topic_id")
    prerequisite_name = prerequisite.get("topic_name")
    prerequisite_score = float(
        prerequisite.get("score", 0)
    )

    prerequisite_resources = get_resources_for_topic(
        resources,
        prerequisite_id,
    )

    duration = calculate_duration(
        priority=prerequisite.get("priority", "medium"),
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
    """Create the main personalized study session."""

    topic_id = topic.get("topic_id")
    topic_name = topic.get("topic_name")
    score = float(topic.get("score", 0))
    priority = topic.get("priority", "medium")

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
    """

    print(
        "\n[Study Plan Agent] "
        "Generating prerequisite-aware study plan..."
    )

    profile = state.get("student_profile", {})
    gaps = state.get("learning_gaps", [])
    resources = state.get("resources", [])
    student_memory = state.get("student_memory", {})

    daily_hours = profile.get("daily_available_hours", 0)
    learning_preference = profile.get(
        "learning_preference",
        "General",
    )

    daily_minutes = int(float(daily_hours or 0) * 60)

    if daily_minutes <= 0:
        print(
            "[Study Plan Agent] "
            "Invalid daily available time."
        )

        return {
            "study_plan": {
                "student_id": profile.get("student_id"),
                "daily_available_hours": daily_hours,
                "sessions": [],
                "total_sessions": 0,
            },
            "next_action": "validation",
        }

    high_priority = [
        gap for gap in gaps
        if gap.get("priority") == "high"
    ]

    medium_priority = [
        gap for gap in gaps
        if gap.get("priority") == "medium"
    ]

    selected_topics = high_priority + medium_priority

    if not selected_topics:
        print(
            "[Study Plan Agent] "
            "No significant learning gaps found."
        )

        return {
            "study_plan": {
                "student_id": profile.get("student_id"),
                "daily_available_hours": daily_hours,
                "sessions": [],
                "total_sessions": 0,
            },
            "next_action": "validation",
        }

    topic_lookup = build_topic_lookup(
        gaps,
        student_memory,
    )

    sessions = []
    scheduled_topic_ids = set()
    current_date = datetime.now().date()

    for topic in selected_topics:
        topic_id = topic.get("topic_id")
        topic_name = topic.get("topic_name")

        if topic_id in scheduled_topic_ids:
            continue

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
                prerequisite_id = prerequisite.get("topic_id")

                if prerequisite_id not in scheduled_topic_ids:
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

                    sessions.append(prerequisite_session)
                    scheduled_topic_ids.add(prerequisite_id)

                    print(
                        "[Study Plan Agent] Prerequisite session: "
                        f"{prerequisite.get('topic_name')} "
                        f"before {topic_name}"
                    )
            else:
                print(
                    "[Study Plan Agent] Prerequisite satisfied: "
                    f"{prerequisite.get('topic_name')} "
                    f"score = {prerequisite.get('score')}"
                )

        target_date = (
            current_date + timedelta(days=len(sessions))
        )

        target_session = create_target_session(
            topic=topic,
            date=target_date,
            daily_minutes=daily_minutes,
            learning_preference=learning_preference,
            resources=resources,
        )

        sessions.append(target_session)
        scheduled_topic_ids.add(topic_id)

        print(
            "[Study Plan Agent] Target session: "
            f"{topic_name} | "
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

    study_plan = {
        "student_id": profile.get("student_id"),
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
