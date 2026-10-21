
import unittest
from unittest.mock import patch

import app.workflows.adaptive_workflow as workflow_module


class TestAdaptiveWorkflowRouting(unittest.TestCase):

    def setUp(self):
        self.calls = []
        self.validation_count = 0

    def make_agent(self, name, action=None):
        def agent(state):
            self.calls.append(name)

            if callable(action):
                return action(state)

            if action is not None:
                return {"next_action": action}

            return {}

        return agent

    def build_test_workflow(self, validation_actions=None):
        validation_actions = validation_actions or ["complete"]
        self.validation_count = 0

        def mock_validation(state):
            self.calls.append("validation")

            index = min(
                self.validation_count,
                len(validation_actions) - 1
            )

            action = validation_actions[index]
            self.validation_count += 1

            return {
                "validation": {"valid": action == "complete"},
                "next_action": action
            }

        replacements = {
            "evaluation_agent": self.make_agent(
                "evaluation", "reflection"
            ),
            "reflection_agent": self.make_agent(
                "reflection", "replan"
            ),
            "memory_agent": self.make_agent("memory"),
            "profile_agent": self.make_agent("profile"),
            "learning_gap_agent": self.make_agent("learning_gap"),
            "resource_agent": self.make_agent("resource"),
            "study_plan_agent": self.make_agent("study_plan"),
            "validation_agent": mock_validation,
            "persistence_agent": self.make_agent(
                "persistence", "complete"
            ),
        }

        patchers = []

        for name, replacement in replacements.items():
            patcher = patch.object(
                workflow_module, name, replacement
            )
            patcher.start()
            patchers.append(patcher)

        self.addCleanup(
            lambda: [patcher.stop() for patcher in reversed(patchers)]
        )

        return workflow_module.build_adaptive_workflow()

    def initial_state(self):
        return {
            "student_id": 1,
            "quiz_result_id": 1,
            "validation_retry_count": 0
        }

    def test_evaluation_can_stop_workflow(self):
        self.calls = []

        with patch.object(
            workflow_module,
            "evaluation_agent",
            side_effect=lambda state: (
                self.calls.append("evaluation")
                or {"next_action": "stop"}
            )
        ):
            graph = workflow_module.build_adaptive_workflow()
            graph.invoke(self.initial_state())

        self.assertEqual(self.calls, ["evaluation"])

    def test_reflection_can_complete_without_replanning(self):
        self.calls = []

        with patch.object(
            workflow_module,
            "evaluation_agent",
            side_effect=lambda state: (
                self.calls.append("evaluation")
                or {"next_action": "reflection"}
            )
        ), patch.object(
            workflow_module,
            "reflection_agent",
            side_effect=lambda state: (
                self.calls.append("reflection")
                or {"next_action": "complete"}
            )
        ):
            graph = workflow_module.build_adaptive_workflow()
            graph.invoke(self.initial_state())

        self.assertEqual(
            self.calls,
            ["evaluation", "reflection"]
        )

    def test_replanning_pipeline_reaches_persistence(self):
        graph = self.build_test_workflow(["complete"])

        graph.invoke(self.initial_state())

        self.assertEqual(
            self.calls,
            [
                "evaluation",
                "reflection",
                "memory",
                "profile",
                "learning_gap",
                "resource",
                "study_plan",
                "validation",
                "persistence",
            ]
        )

    def test_validation_replan_retries_study_plan(self):
        graph = self.build_test_workflow(
            ["replan", "complete"]
        )

        result = graph.invoke(self.initial_state())

        self.assertEqual(self.calls.count("study_plan"), 2)
        self.assertEqual(self.calls.count("validation"), 2)
        self.assertEqual(self.calls.count("persistence"), 1)
        self.assertFalse(
            result.get("validation", {}).get(
                "retry_limit_reached", False
            )
        )

    def test_repeated_validation_failures_stop_after_two_retries(self):
        graph = self.build_test_workflow(["replan"])

        result = graph.invoke(self.initial_state())

        self.assertEqual(self.calls.count("study_plan"), 3)
        self.assertEqual(self.calls.count("validation"), 3)
        self.assertEqual(self.calls.count("persistence"), 0)

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["validation_retry_count"], 2)
        self.assertTrue(
            result["validation"]["retry_limit_reached"]
        )
        self.assertIn(
            "2 replanning attempts",
            result["validation"]["retry_message"]
        )


if __name__ == "__main__":
    unittest.main()
