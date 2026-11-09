import unittest
from unittest.mock import patch

from app.workflows import adaptive_workflow as workflow_module


class TestAdaptiveWorkflowSecurity(unittest.TestCase):


    def test_negative_retry_count_cannot_bypass_limit(self):
        state = {
            "validation_retry_count": -1,
            "next_action": "replan",
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "replan"},
        ):
            result = workflow_module.validation_with_retry(state)

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("validation", result)
        self.assertFalse(result["validation"]["valid"])

    def test_fractional_retry_count_does_not_crash(self):
        state = {
            "validation_retry_count": 1.5,
            "next_action": "replan",
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "replan"},
        ):
            result = workflow_module.validation_with_retry(state)

        self.assertEqual(result["next_action"], "stop")

    def test_string_retry_count_does_not_crash(self):
        state = {
            "validation_retry_count": "invalid",
            "next_action": "replan",
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "replan"},
        ):
            result = workflow_module.validation_with_retry(state)

        self.assertEqual(result["next_action"], "stop")

    def test_boolean_retry_count_is_rejected(self):
        state = {
            "validation_retry_count": True,
            "next_action": "replan",
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "replan"},
        ):
            result = workflow_module.validation_with_retry(state)

        self.assertEqual(result["next_action"], "stop")

    def test_none_validation_result_does_not_trigger_replanning(self):
        state = {
            "validation_retry_count": 0,
            "next_action": "replan",
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value=None,
        ):
            result = workflow_module.validation_with_retry(state)

        self.assertEqual(result["next_action"], "stop")

    def test_list_validation_result_is_handled_safely(self):
        state = {
            "validation_retry_count": 0,
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value=["unexpected"],
        ):
            result = workflow_module.validation_with_retry(state)

        self.assertEqual(result["next_action"], "stop")

    def test_unknown_validation_action_is_rejected(self):
        state = {
            "validation_retry_count": 0,
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "execute_admin"},
        ):
            result = workflow_module.validation_with_retry(state)

        self.assertEqual(result["next_action"], "stop")

    def test_retry_limit_still_allows_exactly_two_retries(self):
        state = {
            "validation_retry_count": 0,
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "replan"},
        ):
            first = workflow_module.validation_with_retry(state)

        self.assertEqual(first["validation_retry_count"], 1)

        second_state = {
            **state,
            **first,
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "replan"},
        ):
            second = workflow_module.validation_with_retry(second_state)

        self.assertEqual(second["validation_retry_count"], 2)

        third_state = {
            **second_state,
            **second,
        }

        with patch.object(
            workflow_module,
            "validation_agent",
            return_value={"next_action": "replan"},
        ):
            third = workflow_module.validation_with_retry(third_state)

        self.assertEqual(third["next_action"], "stop")
        self.assertTrue(
            third["validation"]["retry_limit_reached"]
        )


if __name__ == "__main__":
    unittest.main()