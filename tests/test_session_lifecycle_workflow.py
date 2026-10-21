import unittest
from unittest.mock import patch

from app.workflows.adaptive_workflow import adaptive_workflow


class TestSessionLifecycleWorkflow(unittest.TestCase):

    @patch("app.agents.session_lifecycle_agent.session_lifecycle_agent")
    def test_complete_session_routes_to_lifecycle_agent(self, mock_agent):
        mock_agent.return_value = {
            "session_lifecycle_result": {
                "success": True,
                "item_id": 104,
                "status": "completed",
            }
        }

        result = adaptive_workflow.invoke(
            {
                "workflow_mode": "session_lifecycle",
                "session_action": "complete",
                "session_item_id": 104,
                "student_id": 1,
            }
        )

        self.assertEqual(
            result.get("workflow_mode"),
            "session_lifecycle",
        )
        self.assertEqual(result.get("session_action"), "complete")
        self.assertIsNotNone(result.get("session_lifecycle_result"))

    @patch("app.agents.session_lifecycle_agent.session_lifecycle_agent")
    def test_detect_overdue_routes_to_lifecycle_agent(self, mock_agent):
        mock_agent.return_value = {
            "session_lifecycle_result": {
                "success": True,
                "count": 2,
                "updated_item_ids": [201, 202],
            }
        }

        result = adaptive_workflow.invoke(
            {
                "workflow_mode": "session_lifecycle",
                "session_action": "detect_overdue",
                "student_id": 1,
            }
        )

        self.assertEqual(
            result.get("workflow_mode"),
            "session_lifecycle",
        )
        self.assertEqual(result.get("session_action"), "detect_overdue")
        self.assertIsNotNone(result.get("session_lifecycle_result"))


if __name__ == "__main__":
    unittest.main()
