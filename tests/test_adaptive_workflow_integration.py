
import unittest
from unittest.mock import patch

from app.workflows import adaptive_workflow as workflow_module
from app.agents.study_plan_agent import study_plan_agent
from app.agents.validation_agent import validation_agent
from app.agents.reflection_agent import reflection_agent


class TestAdaptiveWorkflowIntegration(unittest.TestCase):

    def setUp(self):
        self.gaps = [
            {
                "topic_id": 3,
                "topic_name": "Normalization",
                "subject_id": 1,
                "subject_name": "DBMS",
                "score": 40.0,
                "difficulty": 4,
                "status": "weak",
                "priority": "high",
                "prerequisite_topic_id": None,
            }
        ]

        self.persisted_states = []

    def fake_evaluation(self, state):
        return {
            "evaluation": {
                "quiz_result_id": state["quiz_result_id"],
                "student_id": state["student_id"],
                "topic_id": 3,
                "topic_name": "Normalization",
                "score": 40.0,
                "level": "weak",
                "recommended_action": "practice",
                "performance_recorded": True,
            },
            "next_action": "reflection",
        }

    def fake_memory(self, state):
        return {
            "student_memory": {
                "latest_performance": [
                    {
                        "topic_id": 3,
                        "topic_name": "Normalization",
                        "score": 40.0,
                    }
                ]
            }
        }

    def fake_profile(self, state):
        return {
            "student_profile": {
                "student_id": state["student_id"],
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            }
        }

    def fake_learning_gaps(self, state):
        return {
            "learning_gaps": self.gaps,
            "next_action": "resource",
        }

    def fake_resources(self, state):
        return {"resources": []}

    def fake_persistence(self, state):
        self.persisted_states.append(dict(state))

        sessions = state["study_plan"]["sessions"]

        return {
            "persisted_plan": {
                "plan_id": 101,
                "student_id": state["student_id"],
                "status": "active",
                "created_new_plan": True,
                "total_sessions": len(sessions),
            },
            "persistence_action": "created_new_plan",
            "next_action": "complete",
        }

    def build_test_workflow(self):
        patches = [
            patch.object(
                workflow_module,
                "evaluation_agent",
                self.fake_evaluation,
            ),
            patch.object(
                workflow_module,
                "memory_agent",
                self.fake_memory,
            ),
            patch.object(
                workflow_module,
                "profile_agent",
                self.fake_profile,
            ),
            patch.object(
                workflow_module,
                "learning_gap_agent",
                self.fake_learning_gaps,
            ),
            patch.object(
                workflow_module,
                "resource_agent",
                self.fake_resources,
            ),
            patch.object(
                workflow_module,
                "persistence_agent",
                self.fake_persistence,
            ),
        ]

        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        return workflow_module.build_adaptive_workflow()

    def test_weak_quiz_result_reaches_persistence(self):
        workflow = self.build_test_workflow()

        result = workflow.invoke({
            "student_id": 1,
            "quiz_result_id": 123,
        })

        self.assertEqual(result["evaluation"]["level"], "weak")
        self.assertEqual(result["next_action"], "complete")

        plan = result["study_plan"]
        sessions = plan["sessions"]

        self.assertGreater(len(sessions), 0)

        normalization_sessions = [
            session
            for session in sessions
            if session["topic_id"] == 3
        ]

        self.assertTrue(normalization_sessions)

        normalization = normalization_sessions[0]

        self.assertEqual(normalization["priority"], "high")
        self.assertEqual(normalization["learning_status"], "weak")
        self.assertGreater(
            normalization["duration_minutes"],
            0,
        )

        self.assertTrue(result["validation"]["valid"])

        self.assertEqual(
            result["persistence_action"],
            "created_new_plan",
        )

        self.assertEqual(
            result["persisted_plan"]["status"],
            "active",
        )

        self.assertEqual(len(self.persisted_states), 1)

    def test_strong_result_skips_replanning_and_persistence(self):
        workflow = self.build_test_workflow()

        with patch.object(
            workflow_module,
            "evaluation_agent",
            return_value={
                "evaluation": {
                    "quiz_result_id": 124,
                    "student_id": 1,
                    "topic_id": 3,
                    "topic_name": "Normalization",
                    "score": 90.0,
                    "level": "strong",
                    "recommended_action": "maintain",
                },
                "next_action": "reflection",
            },
        ):
            # Rebuild the graph so the strong evaluation is used.
            workflow = workflow_module.build_adaptive_workflow()

            result = workflow.invoke({
                "student_id": 1,
                "quiz_result_id": 124,
            })

        self.assertEqual(result["evaluation"]["level"], "strong")
        self.assertEqual(result["next_action"], "complete")
        self.assertNotIn("study_plan", result)
        self.assertNotIn("persisted_plan", result)
        self.assertEqual(self.persisted_states, [])


if __name__ == "__main__":
    unittest.main()
