
import unittest
from unittest.mock import patch

from app.agents.memory_agent import memory_agent


class TestMemoryAgentSecurity(unittest.TestCase):

    @patch("app.agents.memory_agent.get_student_memory")
    def test_valid_student_memory_loads(self, mock_memory):
        mock_memory.return_value = {
            "student_id": 1,
            "performance_history": [],
        }

        result = memory_agent({"student_id": 1})

        self.assertEqual(
            result["student_memory"],
            mock_memory.return_value,
        )
        self.assertEqual(result["next_action"], "profile")
        mock_memory.assert_called_once_with(1)

    def test_missing_student_id_stops_workflow(self):
        result = memory_agent({})

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)

    def test_non_dictionary_state_stops_workflow(self):
        result = memory_agent(None)

        self.assertEqual(result["next_action"], "stop")

    def test_string_student_id_is_rejected(self):
        result = memory_agent({"student_id": "1"})

        self.assertEqual(result["next_action"], "stop")

    def test_boolean_student_id_is_rejected(self):
        result = memory_agent({"student_id": True})

        self.assertEqual(result["next_action"], "stop")

    def test_zero_student_id_is_rejected(self):
        result = memory_agent({"student_id": 0})

        self.assertEqual(result["next_action"], "stop")

    def test_negative_student_id_is_rejected(self):
        result = memory_agent({"student_id": -1})

        self.assertEqual(result["next_action"], "stop")

    @patch("app.agents.memory_agent.get_student_memory")
    def test_memory_retrieval_exception_stops_workflow(
        self,
        mock_memory,
    ):
        mock_memory.side_effect = RuntimeError(
            "Internal database details"
        )

        result = memory_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["errors"],
            ["Student memory could not be loaded."],
        )

        # Internal exception details must not leak.
        self.assertNotIn(
            "Internal database details",
            str(result),
        )

    @patch("app.agents.memory_agent.get_student_memory")
    def test_memory_error_result_stops_workflow(self, mock_memory):
        mock_memory.return_value = {
            "error": "Internal retrieval error"
        }

        result = memory_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertNotIn(
            "Internal retrieval error",
            str(result),
        )

    @patch("app.agents.memory_agent.get_student_memory")
    def test_invalid_memory_result_stops_workflow(self, mock_memory):
        mock_memory.return_value = None

        result = memory_agent({"student_id": 1})

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)


if __name__ == "__main__":
    unittest.main()
