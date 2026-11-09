
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from app.agents.evaluation_agent import evaluation_agent
from app.database.models import (
    QuizResult,
    Quiz,
    Topic,
    Subject,
    Performance,
)


class FakeQuery:
    def __init__(self, model, record):
        self.model = model
        self.record = record

    def filter(self, *conditions, **kwargs):
        """
        Simulate SQLAlchemy equality filters for test records.

        This ensures ownership filters are actually evaluated
        instead of being silently ignored by the mock.
        """
        if self.record is None:
            return self

        for condition in conditions:
            if not hasattr(condition, "left"):
                continue

            column_name = getattr(condition.left, "key", None)
            expected_value = getattr(condition.right, "value", None)

            if column_name is None:
                continue

            actual_value = getattr(
                self.record,
                column_name,
                None,
            )

            if actual_value != expected_value:
                self.record = None
                break

        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.record


class FakeDatabase:
    def __init__(self, records):
        self.records = records
        self.quiz_result_query_count = 0

    def query(self, model):
        if model == QuizResult:
            self.quiz_result_query_count += 1

            attempts = self.records[QuizResult]

            index = min(
                self.quiz_result_query_count - 1,
                len(attempts) - 1,
            )

            return FakeQuery(model, attempts[index])

        return FakeQuery(
            model,
            self.records.get(model),
        )

    def close(self):
        pass

    def rollback(self):
        pass

    def commit(self):
        pass

    def add(self, record):
        self.records[type(record)] = record

    def refresh(self, record):
        pass


class ConcurrentInsertFakeDatabase(FakeDatabase):
    """
    Simulate another request inserting the quiz-linked performance
    record between our initial lookup and commit.
    """

    def __init__(self, records, competing_performance):
        super().__init__(records)

        self.performance_query_count = 0
        self.competing_performance = competing_performance
        self.commit_attempts = 0

    def query(self, model):
        if model == Performance:
            self.performance_query_count += 1

            # Initial lookup: no record exists yet.
            if self.performance_query_count == 1:
                return FakeQuery(model, None)

            # Recovery lookup: the competing transaction won.
            return FakeQuery(
                model,
                self.records.get(Performance),
            )

        return super().query(model)

    def commit(self):
        self.commit_attempts += 1

        if self.commit_attempts == 1:
            # Simulate the competing transaction committing first.
            self.records[Performance] = self.competing_performance

            raise IntegrityError(
                "INSERT INTO performance",
                {},
                Exception(
                    1062,
                    "Duplicate entry for key "
                    "'uq_performance_quiz_result_id'",
                ),
            )


class TestEvaluationAgent(unittest.TestCase):

    def create_quiz_result(
        self,
        result_id,
        score,
        attempted_at,
    ):
        return SimpleNamespace(
            result_id=result_id,
            student_id=999,
            quiz_id=20,
            score=score,
            attempted_at=attempted_at,
        )

    def create_topic(self):
        return SimpleNamespace(
            topic_id=30,
            topic_name="Test Topic",
            subject_id=10,
        )

    def create_subject(self, student_id=999):
        return SimpleNamespace(
            subject_id=10,
            student_id=student_id,
        )

    def create_quiz(self):
        return SimpleNamespace(
            quiz_id=20,
            topic_id=30,
        )

    def run_evaluation(
        self,
        score,
        quiz_results=None,
        requested_result_id=900,
    ):
        requested_attempt_time = datetime(
            2026,
            10,
            12,
            10,
            0,
            0,
        )

        if quiz_results is None:
            quiz_results = [
                self.create_quiz_result(
                    result_id=900,
                    score=score,
                    attempted_at=requested_attempt_time,
                )
            ]

        requested_attempt = next(
            (
                attempt
                for attempt in quiz_results
                if attempt.result_id == requested_result_id
            ),
            None,
        )

        if requested_attempt is None:
            raise AssertionError(
                "The requested quiz result must exist in test data."
            )

        quiz = self.create_quiz()
        topic = self.create_topic()
        subject = self.create_subject()

        # Simulate an existing performance record linked
        # to the exact quiz result being evaluated.
        performance = SimpleNamespace(
            performance_id=700,
            student_id=requested_attempt.student_id,
            topic_id=topic.topic_id,
            quiz_result_id=requested_attempt.result_id,
            score=requested_attempt.score,
            attempt_date=requested_attempt.attempted_at,
        )

        records = {
            QuizResult: quiz_results,
            Quiz: quiz,
            Topic: topic,
            Subject: subject,
            Performance: performance,
        }

        db = FakeDatabase(records)

        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            result = evaluation_agent({
                "quiz_result_id": requested_result_id,
                "student_id": 999,
            })

        self.assertNotIn("errors", result)
        self.assertEqual(
            result["next_action"],
            "reflection",
        )

        return result["evaluation"], db

    # --------------------------------------------------
    # Score classification tests
    # --------------------------------------------------

    def test_weak_score(self):
        evaluation, _ = self.run_evaluation(40)

        self.assertEqual(
            evaluation["level"],
            "weak",
        )

        self.assertEqual(
            evaluation["recommended_action"],
            "increase_practice",
        )

    def test_moderate_score(self):
        evaluation, _ = self.run_evaluation(60)

        self.assertEqual(
            evaluation["level"],
            "moderate",
        )

        self.assertEqual(
            evaluation["recommended_action"],
            "continue_practice",
        )

    def test_strong_score(self):
        evaluation, _ = self.run_evaluation(90)

        self.assertEqual(
            evaluation["level"],
            "strong",
        )

        self.assertEqual(
            evaluation["recommended_action"],
            "reduce_priority",
        )

    def test_boundary_scores(self):
        cases = [
            (49.99, "weak"),
            (50, "moderate"),
            (74.99, "moderate"),
            (75, "strong"),
        ]

        for score, expected_level in cases:
            with self.subTest(score=score):
                evaluation, _ = self.run_evaluation(score)

                self.assertEqual(
                    evaluation["level"],
                    expected_level,
                )

    # --------------------------------------------------
    # Quiz result selection tests
    # --------------------------------------------------

    def test_evaluates_requested_quiz_result_id(self):
        evaluation, _ = self.run_evaluation(40)

        self.assertEqual(
            evaluation["quiz_result_id"],
            900,
        )

        self.assertEqual(
            evaluation["student_id"],
            999,
        )

        self.assertEqual(
            evaluation["quiz_id"],
            20,
        )

        self.assertEqual(
            evaluation["topic_id"],
            30,
        )

        self.assertEqual(
            evaluation["score"],
            40.0,
        )

    def test_older_requested_attempt_is_not_replaced(self):
        older_attempt = self.create_quiz_result(
            result_id=900,
            score=40,
            attempted_at=datetime(
                2026,
                10,
                12,
                10,
                0,
                0,
            ),
        )

        newer_attempt = self.create_quiz_result(
            result_id=901,
            score=95,
            attempted_at=datetime(
                2026,
                10,
                13,
                10,
                0,
                0,
            ),
        )

        evaluation, db = self.run_evaluation(
            score=40,
            quiz_results=[
                older_attempt,
                newer_attempt,
            ],
            requested_result_id=900,
        )

        self.assertEqual(
            evaluation["quiz_result_id"],
            900,
        )

        self.assertEqual(
            evaluation["score"],
            40.0,
        )

        self.assertEqual(
            evaluation["level"],
            "weak",
        )

        self.assertEqual(
            db.quiz_result_query_count,
            1,
        )

    # --------------------------------------------------
    # Performance persistence tests
    # --------------------------------------------------

    def test_performance_record_is_reused(self):
        evaluation, _ = self.run_evaluation(40)

        self.assertEqual(
            evaluation["performance_id"],
            700,
        )

        self.assertTrue(
            evaluation["performance_recorded"]
        )

    def test_repeated_evaluation_does_not_create_duplicate_performance(
        self,
    ):
        quiz_result = self.create_quiz_result(
            result_id=900,
            score=40,
            attempted_at=datetime(
                2026,
                10,
                12,
                10,
                0,
                0,
            ),
        )

        quiz = self.create_quiz()
        topic = self.create_topic()
        subject = self.create_subject()

        db = FakeDatabase({
            QuizResult: [quiz_result],
            Quiz: quiz,
            Topic: topic,
            Subject: subject,
            Performance: None,
        })

        state = {
            "student_id": 999,
            "quiz_result_id": 900,
            "errors": [],
        }

        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            first_result = evaluation_agent(state)
            second_result = evaluation_agent(state)

        self.assertNotIn(
            "errors",
            first_result,
        )

        self.assertNotIn(
            "errors",
            second_result,
        )

        first_id = first_result["evaluation"]["performance_id"]
        second_id = second_result["evaluation"]["performance_id"]

        self.assertEqual(
            first_id,
            second_id,
        )

        self.assertIsNotNone(
            db.records[Performance]
        )

        self.assertEqual(
            db.records[Performance].quiz_result_id,
            900,
        )

    def test_concurrent_duplicate_insert_reuses_existing_record(self):
        quiz_result = self.create_quiz_result(
            result_id=900,
            score=40,
            attempted_at=datetime(
                2026,
                10,
                12,
                10,
                0,
                0,
            ),
        )

        quiz = self.create_quiz()
        topic = self.create_topic()
        subject = self.create_subject()

        competing_performance = SimpleNamespace(
            performance_id=701,
            student_id=999,
            topic_id=30,
            quiz_result_id=900,
            score=40.0,
            attempt_date=quiz_result.attempted_at,
        )

        db = ConcurrentInsertFakeDatabase(
            records={
                QuizResult: [quiz_result],
                Quiz: quiz,
                Topic: topic,
                Subject: subject,
                Performance: None,
            },
            competing_performance=competing_performance,
        )

        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            result = evaluation_agent({
                "student_id": 999,
                "quiz_result_id": 900,
                "errors": [],
            })

        self.assertNotIn(
            "errors",
            result,
        )

        self.assertEqual(
            result["next_action"],
            "reflection",
        )

        self.assertEqual(
            result["evaluation"]["performance_id"],
            701,
        )

        self.assertTrue(
            result["evaluation"]["performance_recorded"]
        )

        self.assertEqual(
            db.commit_attempts,
            1,
        )

        self.assertIs(
            db.records[Performance],
            competing_performance,
        )

    def test_unrelated_integrity_error_is_not_treated_as_duplicate(
        self,
    ):
        quiz_result = self.create_quiz_result(
            result_id=900,
            score=40,
            attempted_at=datetime(
                2026,
                10,
                12,
                10,
                0,
                0,
            ),
        )

        quiz = self.create_quiz()
        topic = self.create_topic()
        subject = self.create_subject()

        db = FakeDatabase({
            QuizResult: [quiz_result],
            Quiz: quiz,
            Topic: topic,
            Subject: subject,
            Performance: None,
        })

        def fail_commit():
            raise IntegrityError(
                "INSERT INTO performance",
                {},
                Exception(
                    1452,
                    "Foreign key constraint fails",
                ),
            )

        db.commit = fail_commit

        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            result = evaluation_agent({
                "student_id": 999,
                "quiz_result_id": 900,
                "errors": [],
            })

        self.assertIn(
            "errors",
            result,
        )

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        # Updated assertion: the agent returns a sanitized error.
        self.assertIn(
            "Evaluation could not be completed",
            result["errors"][0],
        )

    # --------------------------------------------------
    # Ownership validation tests
    # --------------------------------------------------

    def test_rejects_topic_owned_by_another_student(self):
        quiz_result = self.create_quiz_result(
            result_id=900,
            score=80,
            attempted_at=datetime(
                2026,
                10,
                12,
                10,
                0,
                0,
            ),
        )

        quiz = self.create_quiz()
        topic = self.create_topic()

        # The subject belongs to student 123, not student 999.
        foreign_subject = self.create_subject(
            student_id=123,
        )

        db = FakeDatabase({
            QuizResult: [quiz_result],
            Quiz: quiz,
            Topic: topic,
            Subject: foreign_subject,
            Performance: None,
        })

        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            result = evaluation_agent({
                "student_id": 999,
                "quiz_result_id": 900,
            })

        self.assertIn(
            "errors",
            result,
        )

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        self.assertIn(
            "Quiz topic does not belong to the expected student",
            result["errors"],
        )

        # No performance record should be created for a foreign topic.
        self.assertIsNone(
            db.records[Performance]
        )

    def test_rejects_topic_without_subject(self):
        quiz_result = self.create_quiz_result(
            result_id=900,
            score=80,
            attempted_at=datetime(
                2026,
                10,
                12,
                10,
                0,
                0,
            ),
        )

        quiz = self.create_quiz()
        topic = self.create_topic()

        db = FakeDatabase({
            QuizResult: [quiz_result],
            Quiz: quiz,
            Topic: topic,
            Subject: None,
            Performance: None,
        })

        with patch(
            "app.agents.evaluation_agent.SessionLocal",
            return_value=db,
        ):
            result = evaluation_agent({
                "student_id": 999,
                "quiz_result_id": 900,
            })

        self.assertIn(
            "errors",
            result,
        )

        self.assertEqual(
            result["next_action"],
            "stop",
        )

        self.assertIsNone(
            db.records[Performance]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
