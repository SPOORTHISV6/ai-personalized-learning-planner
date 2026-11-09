
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.session_lifecycle_agent import (
    SAFE_LIFECYCLE_ERROR,
    complete_session,
    detect_overdue_sessions,
    session_lifecycle_agent,
)
from app.database.connection import Base
from app.database.models import (
    Student,
    Subject,
    Topic,
    StudyPlan,
    StudyPlanItem,
)


class TestSessionLifecycleInputSecurity(unittest.TestCase):

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_invalid_student_ids_do_not_open_database(self, mock_session):
        invalid_ids = [None, 0, -1, True, False, "abc", 1.5, "1.5"]

        for student_id in invalid_ids:
            with self.subTest(student_id=student_id):
                result = detect_overdue_sessions(student_id)

                self.assertFalse(result["success"])
                self.assertIn("errors", result)

        mock_session.assert_not_called()

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_invalid_completion_ids_do_not_open_database(
        self, mock_session
    ):
        invalid_ids = [None, 0, -1, True, "abc", 1.5]

        for student_id in invalid_ids:
            with self.subTest(student_id=student_id):
                result = complete_session(student_id, 10)

                self.assertFalse(result["success"])

        for item_id in invalid_ids:
            with self.subTest(item_id=item_id):
                result = complete_session(1, item_id)

                self.assertFalse(result["success"])

        mock_session.assert_not_called()

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_invalid_date_is_rejected_before_database_access(
        self, mock_session
    ):
        result = detect_overdue_sessions(
            student_id=1,
            today="not-a-date",
        )

        self.assertFalse(result["success"])
        self.assertIn("errors", result)
        mock_session.assert_not_called()

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_workflow_rejects_invalid_student_id(self, mock_session):
        result = session_lifecycle_agent({
            "session_action": "complete",
            "student_id": True,
            "session_item_id": 10,
        })

        self.assertEqual(result["next_action"], "stop")
        mock_session.assert_not_called()

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_workflow_rejects_invalid_item_id(self, mock_session):
        result = session_lifecycle_agent({
            "session_action": "complete",
            "student_id": 1,
            "session_item_id": -10,
        })

        self.assertEqual(result["next_action"], "stop")
        mock_session.assert_not_called()


class TestSessionLifecycleDatabaseErrors(unittest.TestCase):

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_overdue_detection_rolls_back_on_database_error(
        self, mock_session_local
    ):
        db = MagicMock()
        mock_session_local.return_value = db

        db.query.side_effect = RuntimeError(
            "Sensitive database connection details"
        )

        result = detect_overdue_sessions(1)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["errors"],
            [SAFE_LIFECYCLE_ERROR],
        )

        db.rollback.assert_called_once()
        db.close.assert_called_once()

        self.assertNotIn(
            "Sensitive database connection details",
            str(result),
        )

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_completion_rolls_back_on_database_error(
        self, mock_session_local
    ):
        db = MagicMock()
        mock_session_local.return_value = db

        db.query.side_effect = RuntimeError(
            "Sensitive database connection details"
        )

        result = complete_session(1, 10)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["errors"],
            [SAFE_LIFECYCLE_ERROR],
        )

        db.rollback.assert_called_once()
        db.close.assert_called_once()

        self.assertNotIn(
            "Sensitive database connection details",
            str(result),
        )


class TestSessionLifecycleSQLiteOwnership(unittest.TestCase):
    """
    Real SQLAlchemy ownership tests using an isolated in-memory
    SQLite database. These tests never connect to the MySQL database.
    """

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        Base.metadata.create_all(bind=self.engine)

        self.TestSessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
        )

        self.session_patch = patch(
            "app.agents.session_lifecycle_agent.SessionLocal",
            self.TestSessionLocal,
        )
        self.session_patch.start()

        self.db = self.TestSessionLocal()

        self.student_one = Student(
            name="Student One",
            email="student_one_test@example.com",
            daily_available_hours=3.0,
            learning_preference="Practice",
        )

        self.student_two = Student(
            name="Student Two",
            email="student_two_test@example.com",
            daily_available_hours=2.0,
            learning_preference="Reading",
        )

        self.db.add_all([
            self.student_one,
            self.student_two,
        ])
        self.db.flush()

        self.subject_one = Subject(
            student_id=self.student_one.student_id,
            subject_name="DBMS One",
        )

        self.subject_two = Subject(
            student_id=self.student_two.student_id,
            subject_name="DBMS Two",
        )

        self.db.add_all([
            self.subject_one,
            self.subject_two,
        ])
        self.db.flush()

        self.topic_one = Topic(
            subject_id=self.subject_one.subject_id,
            topic_name="Normalization One",
            difficulty=3,
        )

        self.topic_two = Topic(
            subject_id=self.subject_two.subject_id,
            topic_name="Normalization Two",
            difficulty=3,
        )

        self.db.add_all([
            self.topic_one,
            self.topic_two,
        ])
        self.db.flush()

        now = datetime.now()

        self.plan_one = StudyPlan(
            student_id=self.student_one.student_id,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=5),
            status="active",
        )

        self.plan_two = StudyPlan(
            student_id=self.student_two.student_id,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=5),
            status="active",
        )

        self.db.add_all([
            self.plan_one,
            self.plan_two,
        ])
        self.db.flush()

        self.student_one_item = StudyPlanItem(
            plan_id=self.plan_one.plan_id,
            topic_id=self.topic_one.topic_id,
            scheduled_date=now - timedelta(days=2),
            duration_minutes=30,
            priority=1,
            status="pending",
        )

        self.student_two_item = StudyPlanItem(
            plan_id=self.plan_two.plan_id,
            topic_id=self.topic_two.topic_id,
            scheduled_date=now - timedelta(days=2),
            duration_minutes=30,
            priority=1,
            status="pending",
        )

        self.db.add_all([
            self.student_one_item,
            self.student_two_item,
        ])
        self.db.commit()

        self.student_one_id = self.student_one.student_id
        self.student_two_id = self.student_two.student_id

        self.student_one_item_id = self.student_one_item.item_id
        self.student_two_item_id = self.student_two_item.item_id

    def tearDown(self):
        self.db.close()
        self.session_patch.stop()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def get_item_status(self, item_id):
        with self.TestSessionLocal() as db:
            item = (
                db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.item_id == item_id
                )
                .one()
            )
            return item.status

    def test_student_cannot_complete_another_students_session(self):
        result = complete_session(
            student_id=self.student_one_id,
            item_id=self.student_two_item_id,
        )

        self.assertFalse(result["success"])

        self.assertEqual(
            self.get_item_status(self.student_two_item_id),
            "pending",
        )

    def test_student_can_complete_own_session(self):
        result = complete_session(
            student_id=self.student_one_id,
            item_id=self.student_one_item_id,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")

        self.assertEqual(
            self.get_item_status(self.student_one_item_id),
            "completed",
        )

    def test_overdue_detection_updates_only_requested_students_sessions(
        self
    ):
        result = detect_overdue_sessions(
            student_id=self.student_one_id,
            today=date.today(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

        self.assertEqual(
            self.get_item_status(self.student_one_item_id),
            "overdue",
        )

        self.assertEqual(
            self.get_item_status(self.student_two_item_id),
            "pending",
        )


if __name__ == "__main__":
    unittest.main()
