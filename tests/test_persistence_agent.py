
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agents import persistence_agent as persistence_module
from app.agents.persistence_agent import (
    SAFE_PERSISTENCE_ERROR,
    persistence_agent,
)
from app.database.models import StudyPlan, StudyPlanItem


class TestPersistenceAgent(unittest.TestCase):

    def setUp(self):
        self.db = MagicMock()

        self.plan_query = MagicMock()
        self.item_query = MagicMock()

        self.db.query.side_effect = self._query_side_effect

        self.plan_query.filter.return_value = self.plan_query
        self.item_query.filter.return_value = self.item_query
        self.item_query.order_by.return_value = self.item_query

        self.plan_query.all.return_value = []
        self.item_query.all.return_value = []

        self.db.add.side_effect = self._assign_generated_ids

    # ---------------------------------------------------------
    # MOCK DATABASE
    # ---------------------------------------------------------

    def _query_side_effect(self, model):

        if model is StudyPlan:
            return self.plan_query

        if model is StudyPlanItem:
            return self.item_query

        raise AssertionError(
            f"Unexpected model queried: {model}"
        )

    def _assign_generated_ids(self, obj):

        if isinstance(obj, StudyPlan):
            obj.plan_id = 101

        elif isinstance(obj, StudyPlanItem):
            obj.item_id = 201

    # ---------------------------------------------------------
    # VALID WORKFLOW STATE
    # ---------------------------------------------------------

    def _valid_state(self):

        return {
            "student_id": 1,

            "study_plan": {
                "student_id": 1,
                "sessions": [
                    {
                        "topic_id": 3,
                        "date": "2026-10-15",
                        "duration_minutes": 60,
                        "priority": "high",
                    }
                ],
            },

            "validation": {
                "valid": True,
                "errors": [],
            },
        }

    # ---------------------------------------------------------
    # HELPER: MOCK OWNED TOPICS
    # ---------------------------------------------------------

    def _mock_owned_topics(self):
        return patch.object(
            persistence_module,
            "get_owned_topic_ids",
            return_value={3},
        )

    # ---------------------------------------------------------
    # TEST 1: CREATE NEW PLAN
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_creates_new_plan(self, mock_session_local):

        mock_session_local.return_value = self.db

        with self._mock_owned_topics():
            result = persistence_agent(self._valid_state())

        self.assertEqual(
            result["persistence_action"],
            "created_new_plan",
        )

        self.assertEqual(
            result["next_action"],
            "complete",
        )

        persisted_plan = result["persisted_plan"]

        self.assertTrue(
            persisted_plan["created_new_plan"]
        )

        self.assertEqual(
            persisted_plan["total_sessions"],
            1,
        )

        self.assertEqual(
            persisted_plan["student_id"],
            1,
        )

        self.assertEqual(
            persisted_plan["items"][0]["topic_id"],
            3,
        )

        self.assertEqual(
            persisted_plan["items"][0]["priority"],
            5,
        )

        self.db.commit.assert_called_once()
        self.db.refresh.assert_called_once()
        self.db.close.assert_called_once()

        added_objects = [
            call.args[0]
            for call in self.db.add.call_args_list
        ]

        self.assertTrue(
            any(
                isinstance(obj, StudyPlan)
                for obj in added_objects
            )
        )

        self.assertTrue(
            any(
                isinstance(obj, StudyPlanItem)
                for obj in added_objects
            )
        )

    # ---------------------------------------------------------
    # TEST 2: SUPERSEDE OLD PLAN
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_supersedes_old_plan_when_creating_replacement(
        self,
        mock_session_local,
    ):

        mock_session_local.return_value = self.db

        old_plan = SimpleNamespace(
            plan_id=50,
            student_id=1,
            status="active",
        )

        self.plan_query.all.return_value = [old_plan]
        self.item_query.all.return_value = []

        with self._mock_owned_topics():
            result = persistence_agent(self._valid_state())

        self.assertEqual(
            old_plan.status,
            "superseded",
        )

        self.assertEqual(
            result["persistence_action"],
            "created_new_plan",
        )

        self.assertEqual(
            result["persisted_plan"]["status"],
            "active",
        )

        self.db.flush.assert_called()
        self.db.commit.assert_called_once()
        self.db.close.assert_called_once()

    # ---------------------------------------------------------
    # TEST 3: REUSE IDENTICAL ACTIVE PLAN
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_reuses_identical_active_plan(
        self,
        mock_session_local,
    ):

        mock_session_local.return_value = self.db

        existing_plan = SimpleNamespace(
            plan_id=50,
            student_id=1,
            start_date=date(2026, 10, 15),
            end_date=date(2026, 10, 15),
            status="active",
        )

        existing_item = SimpleNamespace(
            item_id=501,
            topic_id=3,
            scheduled_date=date(2026, 10, 15),
            duration_minutes=60,
            priority=5,
            status="pending",
        )

        self.plan_query.all.return_value = [existing_plan]
        self.item_query.all.return_value = [existing_item]

        with self._mock_owned_topics():
            result = persistence_agent(self._valid_state())

        self.assertEqual(
            result["persistence_action"],
            "reused",
        )

        self.assertEqual(
            result["next_action"],
            "complete",
        )

        persisted_plan = result["persisted_plan"]

        self.assertFalse(
            persisted_plan["created_new_plan"]
        )

        self.assertEqual(
            persisted_plan["plan_id"],
            50,
        )

        self.assertEqual(
            persisted_plan["total_sessions"],
            1,
        )

        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()

    # ---------------------------------------------------------
    # TEST 4: REJECT FOREIGN TOPIC
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_rejects_foreign_topic_before_modifying_plans(
        self,
        mock_session_local,
    ):

        mock_session_local.return_value = self.db

        old_plan = SimpleNamespace(
            plan_id=50,
            student_id=1,
            status="active",
        )

        self.plan_query.all.return_value = [old_plan]

        with patch.object(
            persistence_module,
            "get_owned_topic_ids",
            return_value=set(),
        ):
            result = persistence_agent(self._valid_state())

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        self.assertIn(
            "do not belong to the current student",
            result["errors"][0],
        )

        # No existing plan must be modified.
        self.assertEqual(
            old_plan.status,
            "active",
        )

        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()

    # ---------------------------------------------------------
    # TEST 5: REJECT INVALID STUDENT ID
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_rejects_invalid_student_id(
        self,
        mock_session_local,
    ):

        state = self._valid_state()
        state["student_id"] = -1

        result = persistence_agent(state)

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        self.assertEqual(
            result["errors"],
            ["Student ID is invalid."],
        )

        mock_session_local.assert_not_called()

    # ---------------------------------------------------------
    # TEST 6: REJECT MISMATCHED PLAN STUDENT ID
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_rejects_plan_with_mismatched_student_id(
        self,
        mock_session_local,
    ):

        state = self._valid_state()
        state["study_plan"]["student_id"] = 2

        result = persistence_agent(state)

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        self.assertIn(
            "does not match",
            result["errors"][0],
        )

        mock_session_local.assert_not_called()

    # ---------------------------------------------------------
    # TEST 7: DATABASE ERROR MUST NOT EXPOSE DETAILS
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_database_exception_is_not_exposed(
        self,
        mock_session_local,
    ):

        mock_session_local.return_value = self.db

        sensitive_error = (
            "mysql://admin:secret-password@localhost/private_db"
        )

        self.db.query.side_effect = RuntimeError(
            sensitive_error
        )

        with self._mock_owned_topics():
            result = persistence_agent(self._valid_state())

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        self.assertEqual(
            result["errors"],
            [SAFE_PERSISTENCE_ERROR],
        )

        self.assertNotIn(
            "secret-password",
            str(result),
        )

        self.db.rollback.assert_called_once()
        self.db.close.assert_called_once()

    # ---------------------------------------------------------
    # TEST 8: ROLLBACK WHEN DATABASE OPERATION FAILS
    # ---------------------------------------------------------

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_rolls_back_when_database_operation_fails(
        self,
        mock_session_local,
    ):

        mock_session_local.return_value = self.db

        self.db.query.side_effect = RuntimeError(
            "Sensitive database connection details"
        )

        with self._mock_owned_topics():
            result = persistence_agent(self._valid_state())

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        self.assertEqual(
            result["errors"],
            [SAFE_PERSISTENCE_ERROR],
        )

        self.db.rollback.assert_called_once()
        self.db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
