
import unittest
from unittest.mock import MagicMock, patch

from app.agents.learning_gap_agent import (
    learning_gap_agent,
    SAFE_ERROR,
)


class TestLearningGapAgentExceptionHandling(unittest.TestCase):

    @patch("app.agents.learning_gap_agent.SessionLocal")
    def test_session_creation_failure(self, mock_session):
        mock_session.side_effect = RuntimeError("Database unavailable")

        result = learning_gap_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["errors"], [SAFE_ERROR])

    @patch("app.agents.learning_gap_agent.SessionLocal")
    @patch("app.agents.learning_gap_agent.calculate_learning_gaps")
    def test_calculation_failure(self, mock_calculate, mock_session):
        db = MagicMock()
        mock_session.return_value = db
        mock_calculate.side_effect = RuntimeError("Query failed")

        result = learning_gap_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["errors"], [SAFE_ERROR])
        db.close.assert_called_once()

    @patch("app.agents.learning_gap_agent.SessionLocal")
    @patch("app.agents.learning_gap_agent.calculate_learning_gaps")
    def test_session_close_failure_does_not_crash(
        self,
        mock_calculate,
        mock_session,
    ):
        db = MagicMock()
        mock_session.return_value = db
        mock_calculate.return_value = []

        db.close.side_effect = RuntimeError("Session close failed")

        result = learning_gap_agent({"student_id": 1})

        self.assertEqual(result["learning_gaps"], [])
        self.assertEqual(result["next_action"], "resource")

    @patch("app.agents.learning_gap_agent.SessionLocal")
    @patch("app.agents.learning_gap_agent.calculate_learning_gaps")
    def test_invalid_result_type_stops_workflow(
        self,
        mock_calculate,
        mock_session,
    ):
        db = MagicMock()
        mock_session.return_value = db
        mock_calculate.return_value = None

        result = learning_gap_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["errors"], [SAFE_ERROR])
        db.close.assert_called_once()

    @patch("app.agents.learning_gap_agent.SessionLocal")
    @patch("app.agents.learning_gap_agent.calculate_learning_gaps")
    def test_invalid_gap_record_stops_workflow(
        self,
        mock_calculate,
        mock_session,
    ):
        db = MagicMock()
        mock_session.return_value = db
        mock_calculate.return_value = [
            {"topic_name": "Normalization"},
            "invalid record",
        ]

        result = learning_gap_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["errors"], [SAFE_ERROR])

    @patch("app.agents.learning_gap_agent.SessionLocal")
    @patch("app.agents.learning_gap_agent.calculate_learning_gaps")
    def test_valid_gaps_are_returned(
        self,
        mock_calculate,
        mock_session,
    ):
        db = MagicMock()
        mock_session.return_value = db

        gaps = [
            {
                "topic_id": 1,
                "topic_name": "Normalization",
                "score": 45.0,
                "status": "weak",
                "priority": "high",
            }
        ]
        mock_calculate.return_value = gaps

        result = learning_gap_agent({"student_id": 1})

        self.assertEqual(result["learning_gaps"], gaps)
        self.assertEqual(result["next_action"], "resource")
        db.close.assert_called_once()

    def test_invalid_student_id_is_rejected(self):
        invalid_ids = [None, 0, -1, True, "1"]

        for student_id in invalid_ids:
            with self.subTest(student_id=student_id):
                result = learning_gap_agent(
                    {"student_id": student_id}
                )

                self.assertEqual(result["next_action"], "stop")


if __name__ == "__main__":
    unittest.main()
