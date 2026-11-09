
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.agents.session_lifecycle_agent import (
    complete_session,
    detect_overdue_sessions,
    session_lifecycle_agent,
)


class TestSessionLifecycleSecurity(unittest.TestCase):

    def setUp(self):
        self.db = MagicMock()

        self.session_local_patcher = patch(
            "app.agents.session_lifecycle_agent.SessionLocal",
            return_value=self.db,
        )
        self.session_local_patcher.start()
        self.addCleanup(self.session_local_patcher.stop)

        self.query = self.db.query.return_value
        self.query.join.return_value = self.query
        self.query.filter.return_value = self.query

    def test_boolean_student_id_is_rejected(self):
        result = complete_session(student_id=True, item_id=10)

        self.assertFalse(result["success"])
        self.db.query.assert_not_called()

    def test_fractional_decimal_student_id_is_rejected(self):
        result = complete_session(
            student_id=Decimal("1.5"),
            item_id=10,
        )

        self.assertFalse(result["success"])
        self.db.query.assert_not_called()

    def test_float_student_id_is_rejected(self):
        result = complete_session(student_id=1.0, item_id=10)

        self.assertFalse(result["success"])
        self.db.query.assert_not_called()

    def test_fractional_decimal_item_id_is_rejected(self):
        result = complete_session(
            student_id=1,
            item_id=Decimal("10.5"),
        )

        self.assertFalse(result["success"])
        self.db.query.assert_not_called()

    def test_boolean_session_item_id_is_rejected(self):
        result = complete_session(student_id=1, item_id=True)

        self.assertFalse(result["success"])
        self.db.query.assert_not_called()

    def test_cross_student_session_is_not_completed(self):
        self.query.first.return_value = None

        result = complete_session(student_id=2, item_id=10)

        self.assertFalse(result["success"])
        self.assertIn("errors", result)
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()

        filter_args = self.query.filter.call_args.args
        filter_conditions = " ".join(
            str(condition) for condition in filter_args
        )

        self.assertIn("study_plans.student_id", filter_conditions)
        self.assertIn("study_plans.status", filter_conditions)

    def test_overdue_detection_filters_by_student_and_active_plan(self):
        self.query.all.return_value = []

        result = detect_overdue_sessions(
            student_id=2,
        )

        self.assertTrue(result["success"])

        filter_args = self.query.filter.call_args.args
        filter_conditions = " ".join(
            str(condition) for condition in filter_args
        )

        self.assertIn("study_plans.student_id", filter_conditions)
        self.assertIn("study_plans.status", filter_conditions)
        self.assertIn("study_plan_items.status", filter_conditions)

    def test_unsupported_session_action_stops_workflow(self):
        result = session_lifecycle_agent({
            "student_id": 1,
            "session_action": "delete",
            "session_item_id": 10,
        })

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)
        self.db.query.assert_not_called()

    def test_non_dictionary_workflow_state_is_rejected(self):
        result = session_lifecycle_agent(["invalid"])

        self.assertEqual(result["next_action"], "stop")
        self.assertIn("errors", result)
        self.db.query.assert_not_called()

    def test_database_failure_returns_safe_error(self):
        self.query.first.side_effect = RuntimeError(
            "Sensitive database connection details"
        )

        result = complete_session(student_id=1, item_id=10)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["errors"],
            [
                "Session lifecycle operation could not be completed. "
                "Please try again later."
            ],
        )

        self.db.rollback.assert_called_once()
        self.db.close.assert_called_once()

        self.assertNotIn(
            "Sensitive database connection details",
            str(result),
        )


if __name__ == "__main__":
    unittest.main()
