
import unittest

from app.agents.reflection_agent import reflection_agent


class TestReflectionAgent(unittest.TestCase):

    def test_missing_evaluation_stops_workflow(self):
        result = reflection_agent({})

        self.assertEqual(
            result["next_action"],
            "stop"
        )
        self.assertIn(
            "Evaluation data is missing",
            result["errors"]
        )

    def test_weak_performance_triggers_replanning(self):
        state = {
            "evaluation": {
                "score": 40,
                "level": "weak",
                "topic_name": "Normalization",
                "recommended_action": "increase_practice"
            }
        }

        result = reflection_agent(state)

        self.assertEqual(
            result["next_action"],
            "replan"
        )
        self.assertIn(
            "weak",
            result["user_feedback"].lower()
        )
        self.assertIn(
            "higher priority",
            result["user_feedback"].lower()
        )

    def test_moderate_performance_triggers_replanning(self):
        state = {
            "evaluation": {
                "score": 60,
                "level": "moderate",
                "topic_name": "SQL Joins",
                "recommended_action": "continue_practice"
            }
        }

        result = reflection_agent(state)

        self.assertEqual(
            result["next_action"],
            "replan"
        )
        self.assertIn(
            "continue practicing",
            result["user_feedback"].lower()
        )

    def test_strong_performance_completes_workflow(self):
        state = {
            "evaluation": {
                "score": 90,
                "level": "strong",
                "topic_name": "Python OOP",
                "recommended_action": "reduce_priority"
            }
        }

        result = reflection_agent(state)

        self.assertEqual(
            result["next_action"],
            "complete"
        )
        self.assertIn(
            "lower priority",
            result["user_feedback"].lower()
        )

    def test_unknown_performance_level_stops_workflow(self):
        state = {
            "evaluation": {
                "score": 65,
                "level": "unknown",
                "topic_name": "Test Topic"
            }
        }

        result = reflection_agent(state)

        self.assertEqual(
            result["next_action"],
            "stop"
        )
        self.assertIn(
            "Unknown performance level: unknown",
            result["errors"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
