
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agents.session_lifecycle_agent import (
    SAFE_LIFECYCLE_ERROR,
    complete_session,
    detect_overdue_sessions,
    session_lifecycle_agent,
)


class TestSessionLifecycleExceptionHandling(unittest.TestCase):

    def make_database(self):
        db = MagicMock()

        query = db.query.return_value
        query.join.return_value = query
        query.filter.return_value = query

        return db, query

    # Database session creation

    @patch(
        "app.agents.session_lifecycle_agent.SessionLocal",
        side_effect=RuntimeError("Database unavailable"),
    )
    def test_overdue_session_creation_failure_returns_safe_error(
        self, mock_session
    ):
        result = detect_overdue_sessions(1)

        self.assertFalse(result["success"])
        self.assertEqual(result["errors"], [SAFE_LIFECYCLE_ERROR])

    @patch(
        "app.agents.session_lifecycle_agent.SessionLocal",
        side_effect=RuntimeError("Database unavailable"),
    )
    def test_completion_session_creation_failure_returns_safe_error(
        self, mock_session
    ):
        result = complete_session(1, 10)

        self.assertFalse(result["success"])
        self.assertEqual(result["errors"], [SAFE_LIFECYCLE_ERROR])

    # Rollback failure

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_overdue_rollback_failure_does_not_escape(self, mock_session):
        db, query = self.make_database()
        mock_session.return_value = db

        query.all.side_effect = RuntimeError("Query failure")
        db.rollback.side_effect = RuntimeError("Rollback failure")

        result = detect_overdue_sessions(1)

        self.assertFalse(result["success"])
        self.assertEqual(result["errors"], [SAFE_LIFECYCLE_ERROR])
        db.rollback.assert_called_once()

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_completion_rollback_failure_does_not_escape(
        self, mock_session
    ):
        db, query = self.make_database()
        mock_session.return_value = db

        query.first.side_effect = RuntimeError("Query failure")
        db.rollback.side_effect = RuntimeError("Rollback failure")

        result = complete_session(1, 10)

        self.assertFalse(result["success"])
        self.assertEqual(result["errors"], [SAFE_LIFECYCLE_ERROR])
        db.rollback.assert_called_once()

    # Database cleanup failure

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_overdue_close_failure_does_not_override_result(
        self, mock_session
    ):
        db, query = self.make_database()
        mock_session.return_value = db

        query.all.return_value = []
        db.close.side_effect = RuntimeError("Close failure")

        result = detect_overdue_sessions(1)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        db.commit.assert_called_once()
        db.close.assert_called_once()

    @patch("app.agents.session_lifecycle_agent.SessionLocal")
    def test_completion_close_failure_does_not_override_result(
        self, mock_session
    ):
        db, query = self.make_database()
        mock_session.return_value = db

        session = SimpleNamespace(
            item_id=10,
            status="pending",
        )
        query.first.return_value = session
        db.close.side_effect = RuntimeError("Close failure")

        result = complete_session(1, 10)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(session.status, "completed")
        db.commit.assert_called_once()
        db.close.assert_called_once()

    # Workflow dispatch failure

    @patch(
        "app.agents.session_lifecycle_agent.detect_overdue_sessions",
        side_effect=RuntimeError("Unexpected dispatch failure"),
    )
    def test_unexpected_dispatch_failure_stops_workflow(
        self, mock_detect
    ):
        result = session_lifecycle_agent({
            "session_action": "detect_overdue",
            "student_id": 1,
        })

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)
        self.assertNotIn("Unexpected dispatch failure", str(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
