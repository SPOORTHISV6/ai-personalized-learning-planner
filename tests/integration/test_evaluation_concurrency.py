
from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.database.models import (
    Student,
    Subject,
    Topic,
    Quiz,
    QuizResult,
    Performance,
)
from tests.integration.test_database import (
    MySQLIntegrationTestCase,
    TestSessionLocal,
)


class TestEvaluationConcurrencyMySQL(MySQLIntegrationTestCase):
    def setUp(self):
        super().setUp()

        self.student = Student(
            name="Concurrency Integration Student",
            email=f"concurrency_{uuid4().hex}@example.test",
            daily_available_hours=2.0,
            learning_preference="Practice",
        )
        self.db.add(self.student)
        self.db.flush()

        self.subject = Subject(
            student_id=self.student.student_id,
            subject_name="Concurrency Test Subject",
            importance=3,
        )
        self.db.add(self.subject)
        self.db.flush()

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="Concurrency Test Topic",
            difficulty=3,
        )
        self.db.add(self.topic)
        self.db.flush()

        self.quiz = Quiz(
            topic_id=self.topic.topic_id,
            title="Concurrency Test Quiz",
            difficulty=2,
        )
        self.db.add(self.quiz)
        self.db.flush()

        self.quiz_result = QuizResult(
            quiz_id=self.quiz.quiz_id,
            student_id=self.student.student_id,
            score=80.0,
            attempted_at=datetime.now().replace(microsecond=0),
        )
        self.db.add(self.quiz_result)
        self.db.commit()

        self.student_id = self.student.student_id
        self.subject_id = self.subject.subject_id
        self.topic_id = self.topic.topic_id
        self.quiz_id = self.quiz.quiz_id
        self.quiz_result_id = self.quiz_result.result_id

    def tearDown(self):
        try:
            self.db.rollback()

            # Remove only the quiz created by this test.
            # Deleting the Quiz through the ORM also deletes its
            # related QuizResult and QuizQuestion records.
            quiz = (
                self.db.query(Quiz)
                .filter_by(quiz_id=self.quiz_id)
                .first()
            )

            if quiz is not None:
                self.db.delete(quiz)
                self.db.flush()

            # Remove the student and their related records.
            # The Student ORM cascades remove performances, subjects,
            # study plans, and quiz results.
            student = (
                self.db.query(Student)
                .filter_by(student_id=self.student_id)
                .first()
            )

            if student is not None:
                self.db.delete(student)
                self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        finally:
            super().tearDown()

    def test_unique_constraint_prevents_duplicate_quiz_performance(
        self,
    ):
        first_db = TestSessionLocal()
        second_db = TestSessionLocal()

        try:
            first_record = Performance(
                student_id=self.student_id,
                topic_id=self.topic_id,
                quiz_result_id=self.quiz_result_id,
                score=80.0,
            )

            second_record = Performance(
                student_id=self.student_id,
                topic_id=self.topic_id,
                quiz_result_id=self.quiz_result_id,
                score=80.0,
            )

            # The first independent session creates the record.
            first_db.add(first_record)
            first_db.commit()

            # The second session cannot create another record for
            # the same quiz result.
            second_db.add(second_record)

            with self.assertRaises(IntegrityError):
                second_db.commit()

            second_db.rollback()

            # Verify the committed database state using the first
            # independent session.
            count = (
                first_db.query(Performance)
                .filter(
                    Performance.quiz_result_id
                    == self.quiz_result_id
                )
                .count()
            )

            self.assertEqual(count, 1)

            stored_record = (
                first_db.query(Performance)
                .filter(
                    Performance.quiz_result_id
                    == self.quiz_result_id
                )
                .one()
            )

            self.assertEqual(
                stored_record.student_id,
                self.student_id,
            )
            self.assertEqual(
                stored_record.topic_id,
                self.topic_id,
            )
            self.assertEqual(stored_record.score, 80.0)

        finally:
            second_db.close()
            first_db.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
