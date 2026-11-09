import unittest
from unittest.mock import patch

from app.workflows import adaptive_workflow as workflow_module


class TestAdaptiveWorkflowRoutingSecurity(unittest.TestCase):

    def test_evaluation_rejects_unknown_action(self):
        with patch.object(
            workflow_module,
            "evaluation_agent",
            return_value={
                "evaluation": {"level": "weak"},
                "next_action": "execute_admin",
            },
        ):
            graph = workflow_module.build_adaptive_workflow()

            result = graph.invoke({
                "student_id": 1,
                "quiz_result_id": 101,
            })

        self.assertEqual(result["next_action"], "stop")

    def test_reflection_rejects_unknown_action(self):
        with patch.object(
            workflow_module,
            "evaluation_agent",
            return_value={
                "evaluation": {"level": "weak"},
                "next_action": "reflection",
            },
        ), patch.object(
            workflow_module,
            "reflection_agent",
            return_value={
                "next_action": "execute_admin",
            },
        ):
            graph = workflow_module.build_adaptive_workflow()

            result = graph.invoke({
                "student_id": 1,
                "quiz_result_id": 102,
            })

        self.assertEqual(result["next_action"], "stop")

    def test_persistence_rejects_unknown_action(self):
        with patch.object(
            workflow_module,
            "evaluation_agent",
            return_value={
                "evaluation": {"level": "weak"},
                "next_action": "reflection",
            },
        ), patch.object(
            workflow_module,
            "reflection_agent",
            return_value={
                "next_action": "replan",
            },
        ), patch.object(
            workflow_module,
            "memory_agent",
            return_value={},
        ), patch.object(
            workflow_module,
            "profile_agent",
            return_value={},
        ), patch.object(
            workflow_module,
            "learning_gap_agent",
            return_value={},
        ), patch.object(
            workflow_module,
            "resource_agent",
            return_value={},
        ), patch.object(
            workflow_module,
            "study_plan_agent",
            return_value={
                "study_plan": {"sessions": []},
            },
        ), patch.object(
            workflow_module,
            "validation_agent",
            return_value={
                "validation": {"valid": True},
                "next_action": "complete",
            },
        ), patch.object(
            workflow_module,
            "persistence_agent",
            return_value={
                "next_action": "execute_admin",
            },
        ):
            graph = workflow_module.build_adaptive_workflow()

            result = graph.invoke({
                "student_id": 1,
                "quiz_result_id": 103,
                "validation_retry_count": 0,
            })

        self.assertEqual(result["next_action"], "stop")


if __name__ == "__main__":
    unittest.main()