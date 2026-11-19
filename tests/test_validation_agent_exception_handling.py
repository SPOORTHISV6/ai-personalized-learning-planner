
import unittest
from unittest.mock import MagicMock, patch

from app.agents.validation_agent import validation_agent


def valid_state():
    return {
        "student_id": 1,
        "student_profile": {
            "student_id": 1,
            "daily_available_hours": 4,
        },
        "study_plan": {
            "student_id": 1,
            "total_sessions": 1,
            "sessions": [
                {
                    "topic_id": 10,
                    "topic_name": "Normalization",
                    "date": "2026-11-17",
                    "duration_minutes": 60,
                    "priority": "high",
                }
            ],
        },
    }


class TestValidationAgentExceptionHandling(unittest.TestCase):

    @patch("app.agents.validation_agent.SessionLocal")
    def test_database_session_creation_failure_is_handled(
        self,
        mock_session,
    ):
        mock_session.side_effect = RuntimeError(
            "Sensitive database connection failure"
        )

        result = validation_agent(valid_state())

        self.assertFalse(result["validation"]["valid"])
        self.assertEqual(result["next_action"], "replan")
        self.assertTrue(
            any(
                "Could not verify topic ownership" in error
                for error in result["validation"]["errors"]
            )
        )

    @patch("app.agents.validation_agent.SessionLocal")
    def test_database_query_failure_is_handled(
        self,
        mock_session,
    ):
        db = MagicMock()
        mock_session.return_value = db

        db.query.side_effect = RuntimeError(
            "Sensitive database query failure"
        )

        result = validation_agent(valid_state())

        self.assertFalse(result["validation"]["valid"])
        self.assertEqual(result["next_action"], "replan")
        self.assertTrue(
            any(
                "Could not verify topic ownership" in error
                for error in result["validation"]["errors"]
            )
        )
        db.close.assert_called_once()

    @patch("app.agents.validation_agent.SessionLocal")
    def test_database_close_failure_does_not_escape(
        self,
        mock_session,
    ):
        db = MagicMock()
        mock_session.return_value = db

        query = db.query.return_value
        joined = query.join.return_value
        filtered = joined.filter.return_value
        filtered.all.return_value = [(10,)]

        db.close.side_effect = RuntimeError(
            "Database cleanup failure"
        )

        result = validation_agent(valid_state())

        self.assertTrue(result["validation"]["valid"])
        self.assertEqual(result["next_action"], "complete")
        db.close.assert_called_once()

    def test_extremely_large_daily_hours_are_handled(self):
        state = valid_state()
        state["student_profile"]["daily_available_hours"] = 10 ** 10000

        result = validation_agent(state)

        self.assertFalse(result["validation"]["valid"])
        self.assertEqual(result["next_action"], "replan")
        self.assertTrue(result["validation"]["errors"])


if __name__ == "__main__":
    unittest.main()
