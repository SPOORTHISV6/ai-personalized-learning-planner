
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agents import persistence_agent as persistence_module
from app.agents.persistence_agent import persistence_agent
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

    def _query_side_effect(self, model):
        if model is StudyPlan:
            return self.plan_query
        if model is StudyPlanItem:
            return self.item_query
        raise AssertionError(f"Unexpected model: {model}")

    def _assign_generated_ids(self, obj):
        if isinstance(obj, StudyPlan):
            obj.plan_id = 101
        elif isinstance(obj, StudyPlanItem):
            obj.item_id = 201

    def _valid_state(self):
        return {
            "student_id": 1,
            "study_plan": {
                "sessions": [
                    {
                        "topic_id": 3,
                        "date": "2026-10-15",
                        "duration_minutes": 60,
                        "priority": "high",
                    }
                ]
            },
            "validation": {"valid": True},
        }

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_creates_new_plan(self, mock_session_local):
        mock_session_local.return_value = self.db

        result = persistence_agent(self._valid_state())

        self.assertEqual(
            result["persistence_action"],
            "created_new_plan",
        )
        self.assertTrue(
            result["persisted_plan"]["created_new_plan"]
        )
        self.assertEqual(
            result["persisted_plan"]["total_sessions"],
            1,
        )
        self.assertEqual(
            result["persisted_plan"]["items"][0]["topic_id"],
            3,
        )
        self.assertEqual(
            result["persisted_plan"]["items"][0]["priority"],
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
            any(isinstance(obj, StudyPlan) for obj in added_objects)
        )
        self.assertTrue(
            any(
                isinstance(obj, StudyPlanItem)
                for obj in added_objects
            )
        )

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_supersedes_old_plan_when_creating_replacement(
        self, mock_session_local
    ):
        mock_session_local.return_value = self.db

        old_plan = SimpleNamespace(
            plan_id=50,
            student_id=1,
            status="active",
        )

        self.plan_query.all.return_value = [old_plan]
        self.item_query.all.return_value = []

        result = persistence_agent(self._valid_state())

        self.assertEqual(old_plan.status, "superseded")
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

    @patch("app.agents.persistence_agent.SessionLocal")
    def test_reuses_identical_active_plan(self, mock_session_local):
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

        result = persistence_agent(self._valid_state())

        self.assertEqual(result["persistence_action"], "reused")
        self.assertFalse(
            result["persisted_plan"]["created_new_plan"]
        )
        self.assertEqual(
            result["persisted_plan"]["plan_id"],
            50,
        )
        self.assertEqual(
            result["persisted_plan"]["total_sessions"],
            1,
        )

        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
