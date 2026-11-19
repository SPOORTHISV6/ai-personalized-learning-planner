
import unittest
from unittest.mock import MagicMock, patch

from app.agents.profile_agent import profile_agent, SAFE_ERROR


class TestProfileAgentExceptionHandling(unittest.TestCase):

    @patch("app.agents.profile_agent.SessionLocal")
    def test_session_creation_failure(self, mock_session):
        mock_session.side_effect = RuntimeError("Database unavailable")

        result = profile_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["errors"], [SAFE_ERROR])

    @patch("app.agents.profile_agent.SessionLocal")
    def test_database_query_failure(self, mock_session):
        db = MagicMock()
        mock_session.return_value = db
        db.query.side_effect = RuntimeError("Query failed")

        result = profile_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["errors"], [SAFE_ERROR])
        db.close.assert_called_once()

    @patch("app.agents.profile_agent.SessionLocal")
    def test_session_close_failure_does_not_crash(self, mock_session):
        db = MagicMock()
        mock_session.return_value = db

        student = MagicMock()
        student.student_id = 1
        student.name = "Test Student"
        student.email = "test@example.com"
        student.daily_available_hours = 4.0
        student.learning_preference = "Practice"

        db.query.return_value.filter.return_value.first.return_value = (
            student
        )
        db.close.side_effect = RuntimeError("Session close failed")

        result = profile_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "learning_gap")
        self.assertEqual(
            result["student_profile"]["student_id"],
            1,
        )

    @patch("app.agents.profile_agent.SessionLocal")
    def test_missing_student_returns_safe_result(self, mock_session):
        db = MagicMock()
        mock_session.return_value = db
        db.query.return_value.filter.return_value.first.return_value = None

        result = profile_agent({"student_id": 999})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["errors"], ["Student not found"])
        db.close.assert_called_once()

    def test_invalid_student_id_is_rejected(self):
        for student_id in [None, 0, -1, True, "1"]:
            with self.subTest(student_id=student_id):
                result = profile_agent({"student_id": student_id})

                self.assertEqual(result["next_action"], "stop")


if __name__ == "__main__":
    unittest.main()
