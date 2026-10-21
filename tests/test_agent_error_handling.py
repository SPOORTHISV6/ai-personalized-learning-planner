
import unittest
from unittest.mock import patch

from app.agents.evaluation_agent import evaluation_agent


class TestEvaluationAgentErrorHandling(unittest.TestCase):

    def test_missing_quiz_result_id(self):
        result = evaluation_agent({})

        self.assertIn("errors", result)
        self.assertIn(
            "Quiz result ID is missing",
            result["errors"],
        )
        self.assertEqual(result["next_action"], "stop")

    @patch("app.agents.evaluation_agent.SessionLocal")
    def test_quiz_result_not_found(self, mock_session_local):
        mock_db = mock_session_local.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = evaluation_agent({
            "quiz_result_id": 999999,
        })

        self.assertIn("errors", result)
        self.assertIn(
            "Quiz result 999999 not found",
            result["errors"],
        )
        self.assertEqual(result["next_action"], "stop")
        mock_db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
