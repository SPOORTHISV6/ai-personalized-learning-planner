
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import (
    Performance,
    Topic,
    Subject,
)


def calculate_learning_gaps(
    student_id: int,
    db: Session,
):
    """
    Calculate learning gaps using only topics owned by
    the given student.

    Both performance ownership and subject ownership
    are verified.

    For each topic, select the latest performance record.
    If multiple records have the same latest timestamp,
    use the highest performance_id as a tie-breaker.
    """

    # Step 1: Find the latest attempt date for each topic
    # belonging to the authenticated student.
    latest_attempt_subquery = (
        db.query(
            Performance.topic_id,
            func.max(
                Performance.attempt_date
            ).label("latest_attempt"),
        )
        .filter(
            Performance.student_id == student_id
        )
        .group_by(
            Performance.topic_id
        )
        .subquery()
    )

    # Step 2: If multiple attempts have the same latest
    # timestamp, select the record with the highest ID.
    latest_performance_subquery = (
        db.query(
            Performance.topic_id,
            func.max(
                Performance.performance_id
            ).label("latest_performance_id"),
        )
        .join(
            latest_attempt_subquery,
            (
                Performance.topic_id
                == latest_attempt_subquery.c.topic_id
            )
            &
            (
                Performance.attempt_date
                == latest_attempt_subquery.c.latest_attempt
            ),
        )
        .filter(
            Performance.student_id == student_id
        )
        .group_by(
            Performance.topic_id
        )
        .subquery()
    )

    # Step 3: Fetch the latest performance records.
    # Verify both performance ownership and topic ownership.
    results = (
        db.query(
            Topic,
            Subject,
            Performance,
        )
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .join(
            Performance,
            Performance.topic_id == Topic.topic_id,
        )
        .join(
            latest_performance_subquery,
            (
                Performance.topic_id
                == latest_performance_subquery.c.topic_id
            )
            &
            (
                Performance.performance_id
                == latest_performance_subquery.c.latest_performance_id
            ),
        )
        .filter(
            Performance.student_id == student_id,
            Subject.student_id == student_id,
        )
        .all()
    )

    # Step 4: Classify learning gaps.
    learning_gaps = []

    for topic, subject, performance in results:

        score = float(performance.score)

        if score < 50:
            status = "weak"
            priority = "high"

        elif score < 75:
            status = "moderate"
            priority = "medium"

        else:
            status = "strong"
            priority = "low"

        # Increase priority for difficult topics
        # where the student's score is below 70.
        if (
            topic.difficulty is not None
            and topic.difficulty >= 4
            and score < 70
        ):
            priority = "high"

        learning_gaps.append(
            {
                "topic_id": topic.topic_id,
                "topic_name": topic.topic_name,
                "subject_id": subject.subject_id,
                "subject_name": subject.subject_name,
                "score": score,
                "difficulty": topic.difficulty,
                "status": status,
                "priority": priority,
                "prerequisite_topic_id": (
                    topic.prerequisite_topic_id
                ),
            }
        )

    # Step 5: Sort by priority.
    priority_order = {
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    learning_gaps.sort(
        key=lambda item: priority_order[item["priority"]]
    )

    return learning_gaps
