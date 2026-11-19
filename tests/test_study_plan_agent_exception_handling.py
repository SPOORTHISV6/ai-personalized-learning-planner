import unittest
from unittest.mock import MagicMock, patch

from app.agents.study_plan_agent import (
    get_owned_topic_ids,
    study_plan_agent,
)


class TestStudyPlanAgentExceptionHandling(unittest.TestCase):

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

    # -----------------------------------------------------
    # DATABASE SESSION CREATION FAILURE
    # -----------------------------------------------------

    @patch(
        "app.agents.study_plan_agent.SessionLocal",
        side_effect=RuntimeError("Database connection failure"),
    )
    def test_database_session_creation_failure_is_propagated(
        self,
        mock_session,
    ):
        with self.assertRaises(RuntimeError):
            get_owned_topic_ids(999)

    # -----------------------------------------------------
    # DATABASE CLEANUP FAILURE
    # -----------------------------------------------------

    @patch("app.agents.study_plan_agent.SessionLocal")
    def test_database_close_failure_does_not_escape(
        self,
        mock_session_local,
    ):
        mock_db = MagicMock()

        mock_session_local.return_value = mock_db

        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            (201, 2)
        ]

        mock_db.close.side_effect = RuntimeError(
            "Database cleanup failure"
        )

        result = get_owned_topic_ids(999)

        self.assertEqual(result, {201})
        mock_db.close.assert_called_once()

    # -----------------------------------------------------
    # PREREQUISITE CYCLE DETECTION FAILURE
    # -----------------------------------------------------

    @patch(
        "app.agents.study_plan_agent.has_prerequisite_cycle",
        side_effect=RuntimeError("Cycle detection failure"),
    )
    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {201},
            "topic_difficulties": {},
            "topic_details": {},
        },
    )
    def test_cycle_detection_failure_stops_workflow(
        self,
        mock_owned,
        mock_cycle,
    ):
        state = self.valid_state()

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["study_plan"]["sessions"],
            [],
        )

        error_text = str(result.get("errors", []))

        self.assertNotIn(
            "Cycle detection failure",
            error_text,
        )

    # -----------------------------------------------------
    # TARGET SESSION GENERATION FAILURE
    # -----------------------------------------------------

    @patch(
        "app.agents.study_plan_agent.create_target_session",
        side_effect=RuntimeError("Target session failure"),
    )
    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {201},
            "topic_difficulties": {},
            "topic_details": {},
        },
    )
    def test_target_session_generation_failure_stops_workflow(
        self,
        mock_owned,
        mock_builder,
    ):
        state = self.valid_state()

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["study_plan"]["sessions"],
            [],
        )

        error_text = str(result.get("errors", []))

        self.assertNotIn(
            "Target session failure",
            error_text,
        )

    # -----------------------------------------------------
    # PREREQUISITE SESSION GENERATION FAILURE
    # -----------------------------------------------------

    @patch(
        "app.agents.study_plan_agent.create_prerequisite_session",
        side_effect=RuntimeError("Prerequisite session failure"),
    )
    @patch(
        "app.agents.study_plan_agent.get_owned_topic_ids",
        return_value={
            "topic_ids": {201, 200},
            "topic_difficulties": {},
            "topic_details": {},
        },
    )
    def test_prerequisite_session_generation_failure_stops_workflow(
        self,
        mock_owned,
        mock_builder,
    ):
        state = self.valid_state()

        state["learning_gaps"][0]["prerequisite_topic_id"] = 200

        state["student_memory"] = {
            "latest_performance": [
                {
                    "topic_id": 200,
                    "topic_name": "Prerequisite Topic",
                    "score": 40,
                }
            ]
        }

        result = study_plan_agent(state)

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["study_plan"]["sessions"],
            [],
        )

        error_text = str(result.get("errors", []))

        self.assertNotIn(
            "Prerequisite session failure",
            error_text,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)