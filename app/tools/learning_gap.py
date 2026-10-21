from sqlalchemy import func

from app.database.connection import SessionLocal
from app.database.models import (
    Performance,
    Topic,
    Subject
)


def calculate_learning_gaps(student_id: int):
    db = SessionLocal()

    try:
        # --------------------------------
        # Find latest performance per topic
        # --------------------------------

        latest_attempt_subquery = (
            db.query(
                Performance.topic_id,
                func.max(
                    Performance.attempt_date
                ).label("latest_attempt")
            )
            .filter(
                Performance.student_id == student_id
            )
            .group_by(
                Performance.topic_id
            )
            .subquery()
        )

        # --------------------------------
        # Get topic + subject + performance
        # --------------------------------

        results = (
            db.query(
                Topic,
                Subject,
                Performance
            )
            .join(
                Subject,
                Topic.subject_id == Subject.subject_id
            )
            .join(
                Performance,
                Performance.topic_id == Topic.topic_id
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
                )
            )
            .filter(
                Performance.student_id == student_id
            )
            .all()
        )

        learning_gaps = []

        # --------------------------------
        # Analyze each topic
        # --------------------------------

        for topic, subject, performance in results:

            score = float(
                performance.score
            )

            # --------------------------------
            # Determine performance status
            # --------------------------------

            if score < 50:
                status = "weak"
                priority = "high"

            elif score < 75:
                status = "moderate"
                priority = "medium"

            else:
                status = "strong"
                priority = "low"

            # --------------------------------
            # Difficulty-based priority
            # --------------------------------

            if (
                topic.difficulty is not None
                and topic.difficulty >= 4
                and score < 70
            ):
                priority = "high"

            # --------------------------------
            # Store learning gap
            # --------------------------------

            learning_gaps.append({
                "topic_id": topic.topic_id,
                "topic_name": topic.topic_name,

                "subject_id": subject.subject_id,
                "subject_name": subject.subject_name,

                "score": score,
                "difficulty": topic.difficulty,

                "status": status,
                "priority": priority,

                "prerequisite_topic_id":
                    topic.prerequisite_topic_id
            })

        # --------------------------------
        # Sort by priority
        # --------------------------------

        priority_order = {
            "high": 1,
            "medium": 2,
            "low": 3
        }

        learning_gaps.sort(
            key=lambda x:
            priority_order[x["priority"]]
        )

        return learning_gaps

    finally:
        db.close()