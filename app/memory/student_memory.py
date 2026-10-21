
from app.database.connection import SessionLocal

from app.database.models import (
    Student,
    Performance,
    Topic,
    StudyPlan,
    StudyPlanItem,
    QuizResult,
    Quiz,
)


def calculate_performance_trends(performance_history):
    """
    Calculate performance trends for each topic.

    Uses all historical performance records while keeping
    the latest attempt as the current performance.
    """
    topic_history = {}

    # Group scores topic-wise.
    for record in performance_history:
        topic_id = record["topic_id"]

        if topic_id not in topic_history:
            topic_history[topic_id] = {
                "topic_id": topic_id,
                "topic_name": record["topic_name"],
                "scores": [],
            }

        topic_history[topic_id]["scores"].append(
            record["score"]
        )

    trends = []

    # Calculate trend information.
    for topic_id, data in topic_history.items():
        scores = data["scores"]

        if not scores:
            continue

        # performance_history is ordered newest first.
        latest_score = scores[0]

        previous_score = (
            scores[1] if len(scores) > 1 else None
        )

        best_score = max(scores)
        average_score = sum(scores) / len(scores)

        # Determine current trend.
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
                "average_score": round(average_score, 2),
                "trend": trend,
            }
        )

    return trends


def get_student_memory(student_id: int):
    db = SessionLocal()

    try:
        # =====================================================
        # 1. STUDENT PROFILE
        # =====================================================

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

        # =====================================================
        # 2. PERFORMANCE HISTORY
        # =====================================================

        performances = (
            db.query(Performance, Topic)
            .join(
                Topic,
                Performance.topic_id == Topic.topic_id,
            )
            .filter(
                Performance.student_id == student_id
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
                    "score": performance.score,
                    "attempt_date": (
                        performance.attempt_date
                    ),
                }
            )

        # =====================================================
        # 3. LATEST PERFORMANCE FOR EACH TOPIC
        # =====================================================

        latest_performance = {}

        for item in performance_history:
            topic_id = item["topic_id"]

            if topic_id not in latest_performance:
                latest_performance[topic_id] = item

        # =====================================================
        # 4. CLASSIFY CURRENT TOPIC PERFORMANCE
        # =====================================================

        weak_topics = []
        moderate_topics = []
        strong_topics = []

        for item in latest_performance.values():
            score = item["score"]

            if score < 50:
                weak_topics.append(item)
            elif score < 75:
                moderate_topics.append(item)
            else:
                strong_topics.append(item)

        # =====================================================
        # 5. PERFORMANCE TRENDS
        # =====================================================

        performance_trends = calculate_performance_trends(
            performance_history
        )

        # =====================================================
        # 6. STUDY PLAN HISTORY
        # =====================================================
        # Preserve all plans for historical tracking.
        # Superseded plans are not deleted.
        # =====================================================

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

        # =====================================================
        # 7. CURRENT STUDY SESSION HISTORY
        # =====================================================
        # Only sessions belonging to active plans are included
        # in session_history.
        #
        # This prevents pending items from superseded plans
        # from appearing as current sessions.
        # Historical plan records remain in the database.
        # =====================================================

        study_sessions = (
            db.query(StudyPlanItem, Topic)
            .join(
                Topic,
                StudyPlanItem.topic_id == Topic.topic_id,
            )
            .join(
                StudyPlan,
                StudyPlanItem.plan_id == StudyPlan.plan_id,
            )
            .filter(
                StudyPlan.student_id == student_id,
                StudyPlan.status == "active",
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

        # =====================================================
        # 8. QUIZ HISTORY
        # =====================================================

        quiz_results = (
            db.query(QuizResult, Quiz, Topic)
            .join(
                Quiz,
                QuizResult.quiz_id == Quiz.quiz_id,
            )
            .join(
                Topic,
                Quiz.topic_id == Topic.topic_id,
            )
            .filter(
                QuizResult.student_id == student_id
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
                    "score": result.score,
                    "attempted_at": result.attempted_at,
                }
            )

        # =====================================================
        # 9. COMPLETE MEMORY OBJECT
        # =====================================================

        memory = {
            "profile": profile,

            # Complete historical performance.
            "performance_history": performance_history,

            # Latest performance for every topic.
            "latest_performance": list(
                latest_performance.values()
            ),

            # Performance trend analysis.
            "performance_trends": performance_trends,

            # Current weak topics.
            "weak_topics": weak_topics,

            # Current moderate topics.
            "moderate_topics": moderate_topics,

            # Current strong topics.
            "strong_topics": strong_topics,

            # All study plans, including superseded plans.
            "study_plan_history": study_plan_history,

            # Sessions from active plans only.
            "session_history": session_history,

            # Previous quiz attempts.
            "quiz_history": quiz_history,
        }

        return memory

    finally:
        db.close()
