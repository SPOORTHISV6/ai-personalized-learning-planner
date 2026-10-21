
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agents.session_lifecycle_agent import (
    complete_session,
    detect_overdue_sessions,
    session_lifecycle_agent,
)


class TestSessionLifecycleAgent(unittest.TestCase):

    def setUp(self):
        self.db = MagicMock()

        self.session_local_patcher = patch(
            "app.agents.session_lifecycle_agent.SessionLocal",
            return_value=self.db,
        )
        self.session_local_patcher.start()
        self.addCleanup(self.session_local_patcher.stop)

        # Match the actual SQLAlchemy query chain:
        # query().join().filter().all()/first()
        self.query = self.db.query.return_value
        self.query.join.return_value = self.query
        self.query.filter.return_value = self.query

    def test_past_pending_session_becomes_overdue(self):
        session = SimpleNamespace(
            item_id=10,
            status="pending",
            scheduled_date=datetime(2026, 10, 10),
        )

        self.query.all.return_value = [session]

        result = detect_overdue_sessions(
            student_id=1,
            today=date(2026, 10, 14),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["updated_item_ids"], [10])
        self.assertEqual(session.status, "overdue")
        self.db.commit.assert_called_once()
        self.db.close.assert_called_once()

    def test_no_past_pending_sessions(self):
        self.query.all.return_value = []

        result = detect_overdue_sessions(
            student_id=1,
            today=date(2026, 10, 14),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["updated_item_ids"], [])
        self.db.commit.assert_called_once()

    def test_session_can_be_completed(self):
        session = SimpleNamespace(
            item_id=10,
            status="pending",
        )
        self.query.first.return_value = session

        result = complete_session(student_id=1, item_id=10)

        self.assertTrue(result["success"])
        self.assertEqual(result["item_id"], 10)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(session.status, "completed")
        self.db.commit.assert_called_once()
        self.db.close.assert_called_once()

    def test_overdue_session_can_be_completed(self):
        session = SimpleNamespace(
            item_id=11,
            status="overdue",
        )
        self.query.first.return_value = session

        result = complete_session(student_id=1, item_id=11)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(session.status, "completed")
        self.db.commit.assert_called_once()

    def test_already_completed_session_is_idempotent(self):
        session = SimpleNamespace(
            item_id=12,
            status="completed",
        )
        self.query.first.return_value = session

        result = complete_session(student_id=1, item_id=12)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["message"],
            "Session is already completed.",
        )
        self.db.commit.assert_not_called()

    def test_session_not_found(self):
        self.query.first.return_value = None

        result = complete_session(student_id=1, item_id=999)

        self.assertFalse(result["success"])
        self.assertIn("errors", result)
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()

    def test_invalid_session_status_cannot_be_completed(self):
        session = SimpleNamespace(
            item_id=13,
            status="cancelled",
        )
        self.query.first.return_value = session

        result = complete_session(student_id=1, item_id=13)

        self.assertFalse(result["success"])
        self.assertIn("errors", result)
        self.db.commit.assert_not_called()

    def test_workflow_dispatches_completion(self):
        with patch(
            "app.agents.session_lifecycle_agent.complete_session",
            return_value={
                "success": True,
                "item_id": 10,
                "status": "completed",
            },
        ) as mock_complete:
            result = session_lifecycle_agent({
                "session_action": "complete",
                "student_id": 1,
                "session_item_id": 10,
            })

        mock_complete.assert_called_once_with(1, 10)
        self.assertEqual(
            result["session_lifecycle_result"]["status"],
            "completed",
        )
        self.assertEqual(result["next_action"], "complete")

    def test_missing_student_id_stops_workflow(self):
        result = session_lifecycle_agent({
            "session_action": "complete",
            "session_item_id": 10,
        })

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)

    def test_missing_item_id_stops_workflow(self):
        result = session_lifecycle_agent({
            "session_action": "complete",
            "student_id": 1,
        })

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)


if __name__ == "__main__":
    unittest.main()
