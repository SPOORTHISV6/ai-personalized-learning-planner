import unittest
from unittest.mock import patch

import app.agents.validation_agent as validation_module

from app.agents.validation_agent import validation_agent


def make_session(
    topic_id=1,
    topic_name="Test Topic",
    date="2026-10-12",
    duration_minutes=60,
    priority="high",
):
    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "date": date,
        "duration_minutes": duration_minutes,
        "priority": priority,
    }


def make_state(
    sessions=None,
    daily_hours=4,
    student_id=999,
    profile_student_id=999,
    plan_student_id=999,
):
    return {
        "student_id": student_id,
        "student_profile": {
            "student_id": profile_student_id,
            "daily_available_hours": daily_hours,
        },
        "study_plan": {
            "student_id": plan_student_id,
            "sessions": sessions if sessions is not None else [
                make_session()
            ],
            "total_sessions": (
                len(sessions) if sessions is not None else 1
            ),
        },
    }


class TestValidationAgentSecurity(unittest.TestCase):

    def setUp(self):
        self.ownership_patcher = patch.object(
            validation_module,
            "get_owned_topic_ids",
            return_value={1, 2, 3},
        )

        self.mock_ownership = self.ownership_patcher.start()
        self.addCleanup(self.ownership_patcher.stop)

    # -------------------------------------------------
    # 1. WORKFLOW STATE VALIDATION
    # -------------------------------------------------

    def test_non_dictionary_state_is_rejected(self):
        result = validation_agent(None)

        self.assertFalse(result["validation"]["valid"])
        self.assertEqual(result["next_action"], "replan")

    def test_missing_student_profile_is_rejected(self):
        state = make_state()
        state["student_profile"] = None

        result = validation_agent(state)

        self.assertFalse(result["validation"]["valid"])

    def test_non_dictionary_study_plan_is_rejected(self):
        state = make_state()
        state["study_plan"] = "invalid"

        result = validation_agent(state)

        self.assertFalse(result["validation"]["valid"])

    def test_non_list_sessions_are_rejected(self):
        state = make_state()
        state["study_plan"]["sessions"] = "invalid"

        result = validation_agent(state)

        self.assertFalse(result["validation"]["valid"])

    def test_non_dictionary_session_is_rejected(self):
        result = validation_agent(
            make_state(sessions=["invalid session"])
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "must be a dictionary" in error
                for error in result["validation"]["errors"]
            )
        )

    # -------------------------------------------------
    # 2. STUDENT ID VALIDATION
    # -------------------------------------------------

    def test_boolean_student_id_is_rejected(self):
        result = validation_agent(
            make_state(student_id=True)
        )

        self.assertFalse(result["validation"]["valid"])

    def test_string_and_integer_student_ids_are_not_equivalent(self):
        result = validation_agent(
            make_state(student_id="999")
        )

        self.assertFalse(result["validation"]["valid"])

    def test_workflow_and_profile_student_ids_must_match(self):
        result = validation_agent(
            make_state(
                student_id=1000,
                profile_student_id=999,
                plan_student_id=1000,
            )
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "student profile" in error.lower()
                or "student ID" in error
                for error in result["validation"]["errors"]
            )
        )

    def test_plan_owner_must_match_workflow_student(self):
        result = validation_agent(
            make_state(
                student_id=999,
                profile_student_id=999,
                plan_student_id=1000,
            )
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "does not match" in error
                for error in result["validation"]["errors"]
            )
        )

    # -------------------------------------------------
    # 3. DAILY STUDY HOURS VALIDATION
    # -------------------------------------------------

    def test_boolean_daily_hours_are_rejected(self):
        result = validation_agent(
            make_state(daily_hours=True)
        )

        self.assertFalse(result["validation"]["valid"])

    def test_nan_daily_hours_are_rejected(self):
        result = validation_agent(
            make_state(daily_hours=float("nan"))
        )

        self.assertFalse(result["validation"]["valid"])

    def test_infinite_daily_hours_are_rejected(self):
        result = validation_agent(
            make_state(daily_hours=float("inf"))
        )

        self.assertFalse(result["validation"]["valid"])

    def test_negative_daily_hours_are_rejected(self):
        result = validation_agent(
            make_state(daily_hours=-2)
        )

        self.assertFalse(result["validation"]["valid"])

    def test_excessive_daily_hours_are_rejected(self):
        result = validation_agent(
            make_state(daily_hours=100)
        )

        self.assertFalse(result["validation"]["valid"])

    # -------------------------------------------------
    # 4. TOPIC VALIDATION
    # -------------------------------------------------

    def test_boolean_topic_id_is_rejected(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(topic_id=True)
                ]
            )
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "invalid topic ID" in error
                for error in result["validation"]["errors"]
            )
        )

    def test_empty_topic_name_is_rejected(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(topic_name="   ")
                ]
            )
        )

        self.assertFalse(result["validation"]["valid"])

    def test_non_string_topic_name_is_rejected(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(topic_name=123)
                ]
            )
        )

        self.assertFalse(result["validation"]["valid"])

    def test_invalid_priority_is_rejected(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(priority="critical")
                ]
            )
        )

        self.assertFalse(result["validation"]["valid"])

    # -------------------------------------------------
    # 5. SESSION DURATION VALIDATION
    # -------------------------------------------------

    def test_boolean_duration_is_rejected(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(duration_minutes=True)
                ]
            )
        )

        self.assertFalse(result["validation"]["valid"])

    def test_fractional_duration_is_rejected(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(duration_minutes=30.5)
                ]
            )
        )

        self.assertFalse(result["validation"]["valid"])

    def test_infinite_duration_is_rejected(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(
                        duration_minutes=float("inf")
                    )
                ]
            )
        )

        self.assertFalse(result["validation"]["valid"])

    def test_excessive_duration_is_rejected_by_daily_limit(self):
        result = validation_agent(
            make_state(
                sessions=[
                    make_session(duration_minutes=500)
                ],
                daily_hours=4,
            )
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "exceeds available study time" in error
                for error in result["validation"]["errors"]
            )
        )

    # -------------------------------------------------
    # 6. STUDY PLAN CONSISTENCY
    # -------------------------------------------------

    def test_duplicate_topic_sessions_are_rejected(self):
        sessions = [
            make_session(
                topic_id=1,
                date="2026-10-12",
            ),
            make_session(
                topic_id=1,
                date="2026-10-13",
            ),
        ]

        result = validation_agent(
            make_state(sessions=sessions)
        )

        self.assertFalse(result["validation"]["valid"])

    def test_total_sessions_mismatch_is_rejected(self):
        state = make_state(
            sessions=[
                make_session(topic_id=1),
                make_session(
                    topic_id=2,
                    date="2026-10-13",
                ),
            ]
        )

        state["study_plan"]["total_sessions"] = 10

        result = validation_agent(state)

        self.assertFalse(result["validation"]["valid"])

    # -------------------------------------------------
    # 7. OWNERSHIP FAILURE HANDLING
    # -------------------------------------------------

    def test_ownership_failure_does_not_expose_exception(self):
        sensitive_message = (
            "Sensitive database connection details"
        )

        self.mock_ownership.side_effect = RuntimeError(
            sensitive_message
        )

        with self.assertLogs(
            validation_module.logger,
            level="WARNING",
        ) as captured:

            result = validation_agent(make_state())

        self.assertFalse(result["validation"]["valid"])

        combined_output = (
            str(result["validation"]["errors"])
            + captured.output.__str__()
        )

        self.assertNotIn(
            sensitive_message,
            combined_output,
        )

        self.assertTrue(
            any(
                "Could not verify topic ownership" in error
                for error in result["validation"]["errors"]
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)