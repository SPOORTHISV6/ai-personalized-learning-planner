import unittest
from unittest.mock import patch

from app.agents.study_plan_agent import (
    build_topic_lookup,
    study_plan_agent,
)


class TestStudyPlanAgentSecurity(unittest.TestCase):

    def valid_state(self):
        return {
            "student_id": 999,
            "student_profile": {
                "student_id": 999,
                "daily_available_hours": 4,
                "learning_preference": "Practice",
            },
            "learning_gaps": [
                {
                    "topic_id": 201,
                    "topic_name": "Weak Topic",
                    "score": 40,
                    "status": "weak",
                    "priority": "high",
                    "prerequisite_topic_id": None,
                }
            ],
            "resources": [],
            "student_memory": {},
        }

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_non_dictionary_state_is_rejected(self, mock_owned):
        result = study_plan_agent(None)

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_boolean_student_id_is_rejected(self, mock_owned):
        state = self.valid_state()
        state["student_id"] = True
        state["student_profile"]["student_id"] = True

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_string_and_integer_student_ids_do_not_match(
        self,
        mock_owned,
    ):
        state = self.valid_state()
        state["student_id"] = "999"

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_malformed_learning_gaps_are_rejected(
        self,
        mock_owned,
    ):
        state = self.valid_state()
        state["learning_gaps"] = "not-a-list"

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_non_dictionary_gap_is_rejected(
        self,
        mock_owned,
    ):
        state = self.valid_state()
        state["learning_gaps"] = ["invalid-gap"]

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

    def test_boolean_score_is_rejected(self):
        gaps = [
            {
                "topic_id": 201,
                "topic_name": "Test Topic",
                "score": True,
            }
        ]

        with self.assertRaises(ValueError):
            build_topic_lookup(gaps, {})

    def test_nan_score_is_rejected(self):
        gaps = [
            {
                "topic_id": 201,
                "topic_name": "Test Topic",
                "score": float("nan"),
            }
        ]

        with self.assertRaises(ValueError):
            build_topic_lookup(gaps, {})

    def test_infinite_score_is_rejected(self):
        gaps = [
            {
                "topic_id": 201,
                "topic_name": "Test Topic",
                "score": float("inf"),
            }
        ]

        with self.assertRaises(ValueError):
            build_topic_lookup(gaps, {})

    def test_score_above_100_is_rejected(self):
        gaps = [
            {
                "topic_id": 201,
                "topic_name": "Test Topic",
                "score": 150,
            }
        ]

        with self.assertRaises(ValueError):
            build_topic_lookup(gaps, {})

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_manipulated_priority_does_not_override_score(
        self,
        mock_owned,
    ):
        state = self.valid_state()

        state["learning_gaps"][0]["score"] = 90
        state["learning_gaps"][0]["status"] = "weak"
        state["learning_gaps"][0]["priority"] = "high"

        result = study_plan_agent(state)

        sessions = result["study_plan"]["sessions"]

        self.assertEqual(sessions, [])

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_boolean_daily_hours_are_rejected(
        self,
        mock_owned,
    ):
        state = self.valid_state()
        state["student_profile"]["daily_available_hours"] = True

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_infinite_daily_hours_are_rejected(
        self,
        mock_owned,
    ):
        state = self.valid_state()
        state["student_profile"]["daily_available_hours"] = float("inf")

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={201},
    )
    def test_excessive_daily_hours_are_rejected(
        self,
        mock_owned,
    ):
        state = self.valid_state()
        state["student_profile"]["daily_available_hours"] = 100

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        side_effect=RuntimeError("Sensitive database connection details"),
    )
    def test_ownership_failure_does_not_leak_exception(
        self,
        mock_owned,
    ):
        state = self.valid_state()

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")

        error_text = str(result.get("errors", []))

        self.assertNotIn(
            "Sensitive database connection details",
            error_text,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)