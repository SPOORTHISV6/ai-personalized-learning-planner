
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from app.database.models import (
    Student,
    Subject,
    Topic,
    StudyPlan,
    StudyPlanItem,
)
from app.agents.session_lifecycle_agent import (
    detect_overdue_sessions,
    complete_session,
)

from tests.integration.test_database import (
    MySQLIntegrationTestCase,
    TestSessionLocal,
)


class TestSessionLifecycleMySQL(MySQLIntegrationTestCase):
    def setUp(self):
        super().setUp()

        # Route lifecycle-agent database access to the test database.
        self.session_patch = patch(
            "app.agents.session_lifecycle_agent.SessionLocal",
            TestSessionLocal,
        )
        self.session_patch.start()

        self.student = Student(
            name="Integration Test Student",
            email=f"integration_{uuid4().hex}@example.test",
            daily_available_hours=2.0,
            learning_preference="Practice",
        )
        self.db.add(self.student)
        self.db.flush()

        self.subject = Subject(
            student_id=self.student.student_id,
            subject_name="Integration Test DBMS",
            importance=3,
        )
        self.db.add(self.subject)
        self.db.flush()

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="Integration Test Normalization",
            difficulty=3,
        )
        self.db.add(self.topic)
        self.db.flush()

        now = datetime.now().replace(microsecond=0)

        self.active_plan = StudyPlan(
            student_id=self.student.student_id,
            start_date=now - timedelta(days=2),
            end_date=now + timedelta(days=5),
            status="active",
        )

        self.superseded_plan = StudyPlan(
            student_id=self.student.student_id,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=2),
            status="superseded",
        )

        self.db.add_all([
            self.active_plan,
            self.superseded_plan,
        ])
        self.db.flush()

        self.overdue_item = StudyPlanItem(
            plan_id=self.active_plan.plan_id,
            topic_id=self.topic.topic_id,
            scheduled_date=now - timedelta(days=1),
            duration_minutes=30,
            priority=1,
            status="pending",
        )

        self.superseded_item = StudyPlanItem(
            plan_id=self.superseded_plan.plan_id,
            topic_id=self.topic.topic_id,
            scheduled_date=now - timedelta(days=1),
            duration_minutes=30,
            priority=1,
            status="pending",
        )

        self.completable_item = StudyPlanItem(
            plan_id=self.active_plan.plan_id,
            topic_id=self.topic.topic_id,
            scheduled_date=now + timedelta(days=1),
            duration_minutes=30,
            priority=1,
            status="pending",
        )

        self.db.add_all([
            self.overdue_item,
            self.superseded_item,
            self.completable_item,
        ])
        self.db.commit()

        self.student_id = self.student.student_id
        self.overdue_item_id = self.overdue_item.item_id
        self.superseded_item_id = self.superseded_item.item_id
        self.completable_item_id = self.completable_item.item_id

    def tearDown(self):
        try:
            # Delete only the student created by this test.
            # ORM cascades remove its subjects, plans, and sessions.
            student = (
                self.db.query(Student)
                .filter_by(student_id=self.student_id)
                .first()
            )

            if student is not None:
                self.db.delete(student)
                self.db.commit()
        finally:
            self.session_patch.stop()
            super().tearDown()
    
    def get_item_status(self, item_id):
        # Discard cached ORM state and read the committed database value.
        self.db.rollback()
        self.db.expire_all()

        item = (
            self.db.query(StudyPlanItem)
            .filter_by(item_id=item_id)
            .populate_existing()
            .one()
        )
        return item.status

    

    def test_overdue_detection_updates_active_plan_only(self):
        result = detect_overdue_sessions(
            self.student_id,
            today=datetime.now().date(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            self.get_item_status(self.overdue_item_id),
            "overdue",
        )
        self.assertEqual(
            self.get_item_status(self.superseded_item_id),
            "pending",
        )

    def test_complete_pending_session(self):
        result = complete_session(
            self.student_id,
            self.completable_item_id,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            self.get_item_status(self.completable_item_id),
            "completed",
        )

    def test_complete_overdue_session(self):
        # First transition the session to overdue.
        detect_overdue_sessions(
            self.student_id,
            today=datetime.now().date(),
        )

        result = complete_session(
            self.student_id,
            self.overdue_item_id,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            self.get_item_status(self.overdue_item_id),
            "completed",
        )

    def test_completion_is_idempotent(self):
        first = complete_session(
            self.student_id,
            self.completable_item_id,
        )
        second = complete_session(
            self.student_id,
            self.completable_item_id,
        )

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(
            self.get_item_status(self.completable_item_id),
            "completed",
        )

    def test_cannot_complete_another_students_session(self):
        other_student = Student(
            name="Other Integration Student",
            email=f"other_{uuid4().hex}@example.test",
            daily_available_hours=1.0,
            learning_preference="Reading",
        )
        self.db.add(other_student)
        self.db.commit()

        try:
            result = complete_session(
                other_student.student_id,
                self.completable_item_id,
            )

            self.assertFalse(result["success"])
            self.assertEqual(
                self.get_item_status(self.completable_item_id),
                "pending",
            )
        finally:
            other_id = other_student.student_id
            self.db.delete(other_student)
            self.db.commit()

    def test_nonexistent_session_is_rejected(self):
        result = complete_session(
            self.student_id,
            999999999,
        )

        self.assertFalse(result["success"])

    def test_invalid_session_status_is_rejected(self):
        self.completable_item.status = "invalid_status"
        self.db.commit()

        result = complete_session(
            self.student_id,
            self.completable_item_id,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            self.get_item_status(self.completable_item_id),
            "invalid_status",
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
