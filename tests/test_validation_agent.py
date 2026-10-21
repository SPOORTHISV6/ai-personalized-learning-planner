
import unittest

from app.agents.validation_agent import validation_agent


def make_state(sessions, daily_hours=4):
    return {
        "student_profile": {
            "student_id": 999,
            "daily_available_hours": daily_hours,
        },
        "study_plan": {
            "student_id": 999,
            "sessions": sessions,
        },
    }


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


class TestValidationAgent(unittest.TestCase):

    def test_valid_plan_is_accepted(self):
        state = make_state([
            make_session(
                date="2026-10-12",
                duration_minutes=60,
            ),
            make_session(
                topic_id=2,
                topic_name="Second Topic",
                date="2026-10-13",
                duration_minutes=45,
                priority="medium",
            ),
        ])

        result = validation_agent(state)

        self.assertTrue(result["validation"]["valid"])
        self.assertEqual(result["validation"]["errors"], [])
        self.assertEqual(result["next_action"], "complete")

    def test_empty_plan_is_rejected(self):
        result = validation_agent(make_state([]))

        self.assertFalse(result["validation"]["valid"])
        self.assertIn(
            "Study plan contains no sessions.",
            result["validation"]["errors"],
        )
        self.assertEqual(result["next_action"], "replan")

    def test_no_available_daily_study_time_is_rejected(self):
        result = validation_agent(
            make_state(
                [make_session()],
                daily_hours=0,
            )
        )

        self.assertFalse(result["validation"]["valid"])
        self.assertIn(
            "Student has no available daily study time.",
            result["validation"]["errors"],
        )

    def test_daily_time_limit_is_enforced(self):
        sessions = [
            make_session(
                topic_id=1,
                date="2026-10-12",
                duration_minutes=150,
            ),
            make_session(
                topic_id=2,
                topic_name="Second Topic",
                date="2026-10-12",
                duration_minutes=100,
            ),
        ]

        result = validation_agent(
            make_state(sessions, daily_hours=4)
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "Study plan exceeds available study time"
                in error
                for error in result["validation"]["errors"]
            )
        )

    def test_invalid_duration_is_rejected(self):
        result = validation_agent(
            make_state([
                make_session(duration_minutes=0),
            ])
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "invalid duration" in error.lower()
                for error in result["validation"]["errors"]
            )
        )

    def test_non_numeric_duration_is_rejected(self):
        result = validation_agent(
            make_state([
                make_session(
                    duration_minutes="not-a-number",
                ),
            ])
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "Invalid duration" in error
                for error in result["validation"]["errors"]
            )
        )

    def test_timestamp_in_date_is_rejected(self):
        result = validation_agent(
            make_state([
                make_session(
                    date="2026-10-12T10:30:00",
                ),
            ])
        )

        self.assertFalse(result["validation"]["valid"])

        self.assertTrue(
            any(
                "contains a timestamp" in error
                for error in result["validation"]["errors"]
            )
        )

    def test_missing_required_field_is_rejected(self):
        session = make_session()
        del session["priority"]

        result = validation_agent(
            make_state([session])
        )

        self.assertFalse(result["validation"]["valid"])
        self.assertIn(
            "Session 1 is missing required field: priority.",
            result["validation"]["errors"],
        )

    def test_missing_date_is_rejected(self):
        session = make_session(date=None)

        result = validation_agent(
            make_state([session])
        )

        self.assertFalse(result["validation"]["valid"])

        errors = result["validation"]["errors"]

        self.assertIn(
            "A study session is missing a scheduled date.",
            errors,
        )
        self.assertIn(
            "Session 1 is missing required field: date.",
            errors,
        )
    
    def test_valid_calendar_date_is_accepted(self):
        result = validation_agent(
            make_state([
                make_session(date="2026-10-12"),
            ])
        )

        self.assertTrue(result["validation"]["valid"])

    def test_impossible_calendar_date_is_rejected(self):
        result = validation_agent(
            make_state([
                make_session(date="2026-99-99"),
            ])
        )

        self.assertFalse(result["validation"]["valid"])
        self.assertTrue(
            any(
                "Invalid session date" in error
                for error in result["validation"]["errors"]
            )
        )

    def test_incorrect_date_format_is_rejected(self):
        result = validation_agent(
            make_state([
                make_session(date="12-10-2026"),
            ])
        )

        self.assertFalse(result["validation"]["valid"])
        self.assertTrue(
            any(
                "YYYY-MM-DD" in error
                for error in result["validation"]["errors"]
            )
        )

    def test_non_padded_date_format_is_rejected(self):
        result = validation_agent(
            make_state([
                make_session(date="2026-1-2"),
            ])
        )

        self.assertFalse(result["validation"]["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
