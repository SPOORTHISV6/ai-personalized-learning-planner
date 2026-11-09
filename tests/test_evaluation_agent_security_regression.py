
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.agents.evaluation_agent import evaluation_agent
from app.database.models import (
    QuizResult,
    Quiz,
    Topic,
    Subject,
    Performance,
)


class FakeQuery:
    def __init__(self, record):
        self.record = record

    def filter(self, *conditions):
        if self.record is None:
            return self

        for condition in conditions:
            if not hasattr(condition, "left"):
                continue

            column_name = getattr(condition.left, "key", None)
            expected_value = getattr(condition.right, "value", None)

            if column_name is None:
                continue

            if getattr(self.record, column_name, None) != expected_value:
                self.record = None
                break

        return self

    def first(self):
        return self.record


class FakeDatabase:
    def __init__(self, records):
        self.records = records
        self.added = []
        self.rollback_called = False

    def query(self, model):
        return FakeQuery(self.records.get(model))

    def add(self, record):
        self.added.append(record)
        self.records[type(record)] = record

    def commit(self):
        pass

    def refresh(self, record):
        pass

    def rollback(self):
        self.rollback_called = True

    def close(self):
        pass


class TestEvaluationAgentSecurityRegression(unittest.TestCase):

    def setUp(self):
        self.quiz_result = SimpleNamespace(
            result_id=900,
            student_id=999,
            quiz_id=20,
            score=40,
            attempted_at=datetime(2026, 10, 12, 10, 0),
        )

        self.quiz = SimpleNamespace(
            quiz_id=20,
            topic_id=30,
        )

        self.topic = SimpleNamespace(
            topic_id=30,
            topic_name="Normalization",
            subject_id=10,
        )

        self.subject = SimpleNamespace(
            subject_id=10,
            student_id=999,
        )

    def create_database(self, performance):
        return FakeDatabase({
            QuizResult: self.quiz_result,
            Quiz: self.quiz,
            Topic: self.topic,
            Subject: self.subject,
            Performance: performance,
        })

    def run_agent(self, db):
        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            return evaluation_agent({
                "student_id": 999,
                "quiz_result_id": 900,
            })

    def test_rejects_existing_performance_owned_by_another_student(self):
        performance = SimpleNamespace(
            performance_id=700,
            student_id=123,
            topic_id=30,
            quiz_result_id=900,
            score=50,
            attempt_date=self.quiz_result.attempted_at,
        )

        db = self.create_database(performance)

        result = self.run_agent(db)

        self.assertEqual(result["next_action"], "stop")
        self.assertIn(
            "Existing performance record has an ownership mismatch",
            result["errors"],
        )

        self.assertEqual(performance.student_id, 123)
        self.assertEqual(performance.score, 50)
        self.assertEqual(db.added, [])

    def test_rejects_existing_performance_with_different_topic(self):
        performance = SimpleNamespace(
            performance_id=700,
            student_id=999,
            topic_id=45,
            quiz_result_id=900,
            score=50,
            attempt_date=self.quiz_result.attempted_at,
        )

        db = self.create_database(performance)

        result = self.run_agent(db)

        self.assertEqual(result["next_action"], "stop")
        self.assertIn(
            "Existing performance record has an ownership mismatch",
            result["errors"],
        )

        self.assertEqual(performance.topic_id, 45)
        self.assertEqual(performance.score, 50)

    def test_valid_existing_performance_is_reused(self):
        performance = SimpleNamespace(
            performance_id=700,
            student_id=999,
            topic_id=30,
            quiz_result_id=900,
            score=50,
            attempt_date=self.quiz_result.attempted_at,
        )

        db = self.create_database(performance)

        result = self.run_agent(db)

        self.assertEqual(result["next_action"], "reflection")
        self.assertEqual(
            result["evaluation"]["performance_id"],
            700,
        )
        self.assertEqual(performance.student_id, 999)
        self.assertEqual(performance.topic_id, 30)
        self.assertEqual(performance.score, 40.0)

    def test_unexpected_database_error_is_sanitized(self):
        db = self.create_database(None)

        def fail_commit():
            raise RuntimeError(
                "mysql://private-user:secret@localhost/internal_db"
            )

        db.commit = fail_commit

        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            result = evaluation_agent({
                "student_id": 999,
                "quiz_result_id": 900,
            })

        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(
            result["errors"],
            [
                "Evaluation could not be completed. "
                "Please try again later."
            ],
        )

        self.assertNotIn("secret", str(result["errors"]))
        self.assertTrue(db.rollback_called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
