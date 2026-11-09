from app.database.connection import SessionLocal

from app.database.models import (
    Student,
    Performance,
    Topic,
    Subject,
    StudyPlan,
    StudyPlanItem,
    QuizResult,
    Quiz,
)


def calculate_performance_trends(performance_history):
    """
    Calculate performance trends for each topic.

    Uses historical performance records while treating the
    latest attempt as the current performance.
    """

    topic_history = {}

    # Group performance records topic-wise.
    for record in performance_history:

        topic_id = record["topic_id"]

        if topic_id not in topic_history:
            topic_history[topic_id] = {
                "topic_id": topic_id,
                "topic_name": record["topic_name"],
                "scores": [],
            }

        topic_history[topic_id]["scores"].append(
            float(record["score"])
        )

    trends = []

    for topic_id, data in topic_history.items():

        scores = data["scores"]

        if not scores:
            continue

        # Records are ordered newest first.
        latest_score = scores[0]

        previous_score = (
            scores[1] if len(scores) > 1 else None
        )

        best_score = max(scores)
        average_score = sum(scores) / len(scores)

        if previous_score is None:
            trend = "insufficient_data"

        elif latest_score > previous_score:
            trend = "improving"

        elif latest_score < previous_score:
            trend = "declining"

        else:
            trend = "stable"

        trends.append(
            {
                "topic_id": topic_id,
                "topic_name": data["topic_name"],
                "attempts": len(scores),
                "latest_score": latest_score,
                "previous_score": previous_score,
                "best_score": best_score,
                "average_score": round(
                    average_score,
                    2,
                ),
                "trend": trend,
            }
        )

    return trends


def get_student_memory(student_id: int):
    """
    Retrieve student-specific learning memory.

    All topic-related queries verify ownership through:

        Performance / StudyPlan / QuizResult
                    |
                  Topic
                    |
                  Subject
                    |
             Subject.student_id

    Historical records are preserved. This function only filters
    what is returned to the requested student's memory.
    """

    db = SessionLocal()

    try:

        # ==================================================
        # 1. STUDENT PROFILE
        # ==================================================

        student = (
            db.query(Student)
            .filter(
                Student.student_id == student_id
            )
            .first()
        )

        if not student:
            return {
                "error": f"Student {student_id} not found"
            }

        profile = {
            "student_id": student.student_id,
            "name": student.name,
            "email": student.email,
            "daily_available_hours": (
                student.daily_available_hours
            ),
            "learning_preference": (
                student.learning_preference
            ),
        }

        # ==================================================
        # 2. PERFORMANCE HISTORY
        # ==================================================
        # Both performance ownership and topic ownership
        # must match the requested student.
        # ==================================================

        performances = (
            db.query(
                Performance,
                Topic,
            )
            .join(
                Topic,
                Performance.topic_id == Topic.topic_id,
            )
            .join(
                Subject,
                Topic.subject_id == Subject.subject_id,
            )
            .filter(
                Performance.student_id == student_id,
                Subject.student_id == student_id,
            )
            .order_by(
                Performance.attempt_date.desc()
            )
            .all()
        )

        performance_history = []

        for performance, topic in performances:

            performance_history.append(
                {
                    "topic_id": topic.topic_id,
                    "topic_name": topic.topic_name,
                    "score": float(performance.score),
                    "attempt_date": (
                        performance.attempt_date
                    ),
                }
            )

        # ==================================================
        # 3. LATEST PERFORMANCE PER TOPIC
        # ==================================================

        latest_performance = {}

        for item in performance_history:

            topic_id = item["topic_id"]

            if topic_id not in latest_performance:
                latest_performance[topic_id] = item

        latest_performance_list = list(
            latest_performance.values()
        )

        # ==================================================
        # 4. CLASSIFY CURRENT TOPIC PERFORMANCE
        # ==================================================

        weak_topics = []
        moderate_topics = []
        strong_topics = []

        for item in latest_performance_list:

            score = float(item["score"])

            if score < 50:
                weak_topics.append(item)

            elif score < 75:
                moderate_topics.append(item)

            else:
                strong_topics.append(item)

        # ==================================================
        # 5. PERFORMANCE TRENDS
        # ==================================================

        performance_trends = calculate_performance_trends(
            performance_history
        )

        # ==================================================
        # 6. STUDY PLAN HISTORY
        # ==================================================
        # Preserve all plan records.
        # Superseded plans are not deleted.
        # ==================================================

        study_plans = (
            db.query(StudyPlan)
            .filter(
                StudyPlan.student_id == student_id
            )
            .order_by(
                StudyPlan.created_at.desc()
            )
            .all()
        )

        study_plan_history = []

        for plan in study_plans:

            study_plan_history.append(
                {
                    "plan_id": plan.plan_id,
                    "start_date": plan.start_date,
                    "end_date": plan.end_date,
                    "status": plan.status,
                }
            )

        # ==================================================
        # 7. CURRENT STUDY SESSION HISTORY
        # ==================================================
        # Only active plans and topics belonging to this
        # student are returned.
        # ==================================================

        study_sessions = (
            db.query(
                StudyPlanItem,
                Topic,
            )
            .join(
                Topic,
                StudyPlanItem.topic_id == Topic.topic_id,
            )
            .join(
                Subject,
                Topic.subject_id == Subject.subject_id,
            )
            .join(
                StudyPlan,
                StudyPlanItem.plan_id == StudyPlan.plan_id,
            )
            .filter(
                StudyPlan.student_id == student_id,
                StudyPlan.status == "active",
                Subject.student_id == student_id,
            )
            .order_by(
                StudyPlanItem.scheduled_date.desc()
            )
            .all()
        )

        session_history = []

        for session, topic in study_sessions:

            session_history.append(
                {
                    "plan_id": session.plan_id,
                    "item_id": session.item_id,
                    "topic_id": topic.topic_id,
                    "topic_name": topic.topic_name,
                    "scheduled_date": (
                        session.scheduled_date
                    ),
                    "duration_minutes": (
                        session.duration_minutes
                    ),
                    "priority": session.priority,
                    "status": session.status,
                }
            )

        # ==================================================
        # 8. QUIZ HISTORY
        # ==================================================
        # Only quiz results associated with topics owned
        # by the requested student are included.
        # ==================================================

        quiz_results = (
            db.query(
                QuizResult,
                Quiz,
                Topic,
            )
            .join(
                Quiz,
                QuizResult.quiz_id == Quiz.quiz_id,
            )
            .join(
                Topic,
                Quiz.topic_id == Topic.topic_id,
            )
            .join(
                Subject,
                Topic.subject_id == Subject.subject_id,
            )
            .filter(
                QuizResult.student_id == student_id,
                Subject.student_id == student_id,
            )
            .order_by(
                QuizResult.attempted_at.desc()
            )
            .all()
        )

        quiz_history = []

        for result, quiz, topic in quiz_results:

            quiz_history.append(
                {
                    "quiz_id": quiz.quiz_id,
                    "quiz_title": quiz.title,
                    "topic_id": topic.topic_id,
                    "topic_name": topic.topic_name,
                    "score": float(result.score),
                    "attempted_at": result.attempted_at,
                }
            )

        # ==================================================
        # 9. COMPLETE MEMORY OBJECT
        # ==================================================

        memory = {
            "profile": profile,

            "performance_history": (
                performance_history
            ),

            "latest_performance": (
                latest_performance_list
            ),

            "performance_trends": (
                performance_trends
            ),

            "weak_topics": weak_topics,

            "moderate_topics": moderate_topics,

            "strong_topics": strong_topics,

            "study_plan_history": (
                study_plan_history
            ),

            "session_history": (
                session_history
            ),

            "quiz_history": (
                quiz_history
            ),
        }

        return memory

    finally:
        db.close()