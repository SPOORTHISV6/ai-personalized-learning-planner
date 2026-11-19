
import unittest
from unittest.mock import MagicMock, patch

from app.agents.persistence_agent import (
    SAFE_PERSISTENCE_ERROR,
    normalize_session_details,
    persistence_agent,
)


def valid_state():
    return {
        "student_id": 1,
        "study_plan": {
            "student_id": 1,
            "sessions": [
                {
                    "topic_id": 10,
                    "date": "2026-11-17",
                    "duration_minutes": 60,
                    "priority": "high",
                    "score": 45.0,
                }
            ],
        },
        "validation": {
            "valid": True,
        },
    }


class TestPersistenceAgentExceptionHandling(unittest.TestCase):

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_database_session_creation_failure(self, mock_session):
        mock_session.side_effect = RuntimeError(
            "Database connection failed"
        )

        result = persistence_agent(valid_state())

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["errors"],
            [SAFE_PERSISTENCE_ERROR],
        )

    @patch("app.agents.persistence_agent.get_owned_topic_ids")
    @patch("app.agents.persistence_agent.SessionLocal")
    def test_rollback_failure_does_not_escape(
        self,
        mock_session,
        mock_ownership,
    ):
        db = MagicMock()
        mock_session.return_value = db

        mock_ownership.side_effect = RuntimeError(
            "Sensitive database failure"
        )
        db.rollback.side_effect = RuntimeError(
            "Rollback failed"
        )

        result = persistence_agent(valid_state())

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["errors"],
            [SAFE_PERSISTENCE_ERROR],
        )
        db.rollback.assert_called_once()

    @patch("app.agents.persistence_agent.get_owned_topic_ids")
    @patch("app.agents.persistence_agent.SessionLocal")
    def test_database_close_failure_does_not_escape(
        self,
        mock_session,
        mock_ownership,
    ):
        db = MagicMock()
        mock_session.return_value = db

        mock_ownership.side_effect = RuntimeError(
            "Database query failed"
        )
        db.close.side_effect = RuntimeError(
            "Database close failed"
        )

        result = persistence_agent(valid_state())

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["errors"],
            [SAFE_PERSISTENCE_ERROR],
        )
        db.close.assert_called_once()

    def test_nan_score_is_normalized_to_none(self):
        details = normalize_session_details({
            "score": float("nan"),
        })

        self.assertIsNone(details["score"])

    def test_infinite_score_is_normalized_to_none(self):
        for score in (float("inf"), float("-inf")):
            with self.subTest(score=score):
                details = normalize_session_details({
                    "score": score,
                })

                self.assertIsNone(details["score"])


if __name__ == "__main__":
    unittest.main()
