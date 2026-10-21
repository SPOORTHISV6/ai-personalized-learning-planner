
from sqlalchemy import func

from app.database.connection import SessionLocal
from app.database.models import (
    Student,
    StudyPlan,
    StudyPlanItem,
)


def inspect_database():
    db = SessionLocal()

    try:
        print("\n=== DATABASE LIFECYCLE INSPECTION ===")

        student_count = db.query(func.count(Student.student_id)).scalar()
        plan_count = db.query(func.count(StudyPlan.plan_id)).scalar()
        item_count = db.query(
            func.count(StudyPlanItem.item_id)
        ).scalar()

        print(f"Students: {student_count}")
        print(f"Study plans: {plan_count}")
        print(f"Study plan items: {item_count}")

        print("\n=== STUDY PLAN STATUS COUNTS ===")
        plan_statuses = (
            db.query(
                StudyPlan.status,
                func.count(StudyPlan.plan_id),
            )
            .group_by(StudyPlan.status)
            .all()
        )

        for status, count in plan_statuses:
            print(f"{status}: {count}")

        print("\n=== SESSION STATUS COUNTS ===")
        session_statuses = (
            db.query(
                StudyPlanItem.status,
                func.count(StudyPlanItem.item_id),
            )
            .group_by(StudyPlanItem.status)
            .all()
        )

        for status, count in session_statuses:
            print(f"{status}: {count}")

        print("\n=== RECENT STUDY PLANS ===")
        plans = (
            db.query(StudyPlan)
            .order_by(StudyPlan.plan_id.desc())
            .limit(10)
            .all()
        )

        for plan in plans:
            print(
                f"Plan ID={plan.plan_id}, "
                f"Student ID={plan.student_id}, "
                f"Status={plan.status}, "
                f"Start={plan.start_date}, "
                f"End={plan.end_date}"
            )

        print("\n=== RECENT STUDY SESSIONS ===")
        items = (
            db.query(StudyPlanItem)
            .order_by(StudyPlanItem.item_id.desc())
            .limit(15)
            .all()
        )

        for item in items:
            print(
                f"Item ID={item.item_id}, "
                f"Plan ID={item.plan_id}, "
                f"Topic ID={item.topic_id}, "
                f"Scheduled={item.scheduled_date}, "
                f"Status={item.status}"
            )

    except Exception as exc:
        print(f"Inspection failed: {exc}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    inspect_database()
