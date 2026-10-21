from datetime import datetime, timedelta

from app.database.connection import SessionLocal
from app.database.models import (
    Student,
    Subject,
    Topic,
    Performance,
    StudyPlan,
    StudyPlanItem,
    Quiz,
    QuizResult,
    Resource
)


def seed_database():
    db = SessionLocal()

    try:
        # --------------------------------------------------
        # 1. STUDENT
        # --------------------------------------------------

        student = Student(
            name="Rahul",
            email="rahul@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice"
        )

        db.add(student)
        db.commit()
        db.refresh(student)

        print(f"Student created: {student.student_id}")

        # --------------------------------------------------
        # 2. SUBJECTS
        # --------------------------------------------------

        dbms = Subject(
            student_id=student.student_id,
            subject_name="DBMS",
            exam_date=datetime(2026, 12, 10),
            importance=5
        )

        python = Subject(
            student_id=student.student_id,
            subject_name="Python",
            exam_date=datetime(2026, 12, 15),
            importance=4
        )

        db.add_all([dbms, python])
        db.commit()

        db.refresh(dbms)
        db.refresh(python)

        print("Subjects created")

        # --------------------------------------------------
        # 3. TOPICS
        # --------------------------------------------------

        sql = Topic(
            subject_id=dbms.subject_id,
            topic_name="SQL Basics",
            difficulty=2
        )

        db.add(sql)
        db.commit()
        db.refresh(sql)

        joins = Topic(
            subject_id=dbms.subject_id,
            topic_name="SQL Joins",
            difficulty=3,
            prerequisite_topic_id=sql.topic_id
        )

        normalization = Topic(
            subject_id=dbms.subject_id,
            topic_name="Normalization",
            difficulty=4,
            prerequisite_topic_id=sql.topic_id
        )

        python_oop = Topic(
            subject_id=python.subject_id,
            topic_name="Python OOP",
            difficulty=3
        )

        db.add_all([
            joins,
            normalization,
            python_oop
        ])

        db.commit()

        db.refresh(joins)
        db.refresh(normalization)
        db.refresh(python_oop)

        print("Topics created")

        # --------------------------------------------------
        # 4. PERFORMANCE
        # --------------------------------------------------

        performance1 = Performance(
            student_id=student.student_id,
            topic_id=sql.topic_id,
            score=85
        )

        performance2 = Performance(
            student_id=student.student_id,
            topic_id=joins.topic_id,
            score=60
        )

        performance3 = Performance(
            student_id=student.student_id,
            topic_id=normalization.topic_id,
            score=45
        )

        performance4 = Performance(
            student_id=student.student_id,
            topic_id=python_oop.topic_id,
            score=72
        )

        db.add_all([
            performance1,
            performance2,
            performance3,
            performance4
        ])

        db.commit()

        print("Performance data created")

        # --------------------------------------------------
        # 5. STUDY PLAN
        # --------------------------------------------------

        today = datetime.now()

        plan = StudyPlan(
            student_id=student.student_id,
            start_date=today,
            end_date=today + timedelta(days=7),
            status="active"
        )

        db.add(plan)
        db.commit()
        db.refresh(plan)

        print("Study plan created")

        # --------------------------------------------------
        # 6. STUDY PLAN ITEMS
        # --------------------------------------------------

        item1 = StudyPlanItem(
            plan_id=plan.plan_id,
            topic_id=normalization.topic_id,
            scheduled_date=today,
            duration_minutes=60,
            priority=5,
            status="pending"
        )

        item2 = StudyPlanItem(
            plan_id=plan.plan_id,
            topic_id=joins.topic_id,
            scheduled_date=today + timedelta(days=1),
            duration_minutes=45,
            priority=3,
            status="pending"
        )

        db.add_all([item1, item2])
        db.commit()

        print("Study plan items created")

        # --------------------------------------------------
        # 7. QUIZ
        # --------------------------------------------------

        quiz = Quiz(
            topic_id=normalization.topic_id,
            title="Normalization Quiz",
            difficulty=3
        )

        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        print("Quiz created")

        # --------------------------------------------------
        # 8. QUIZ RESULT
        # --------------------------------------------------

        quiz_result = QuizResult(
            quiz_id=quiz.quiz_id,
            student_id=student.student_id,
            score=45
        )

        db.add(quiz_result)
        db.commit()

        print("Quiz result created")

        # --------------------------------------------------
        # 9. RESOURCE
        # --------------------------------------------------

        resource = Resource(
            topic_id=normalization.topic_id,
            title="Normalization Study Material",
            resource_type="PDF",
            source="Internal",
            content_path="data/documents/normalization.pdf"
        )

        db.add(resource)
        db.commit()

        print("Resource created")

        print("\nDatabase seeded successfully!")

    except Exception as e:
        db.rollback()
        print("Error while seeding database:")
        print(e)

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()