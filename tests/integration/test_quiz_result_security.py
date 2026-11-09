import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import quiz_result_routes
from app.api.dependencies import get_current_student
from app.database.connection import Base
from app.database.models import (
    Student,
    Subject,
    Topic,
    Quiz,
    QuizQuestion,
    QuizResult,
    QuizAnswer,
)
from app.main import app

from tests.integration.test_database import (
    TestSessionLocal,
    test_engine,
    verify_test_database,
)


SAFE_WORKFLOW_ERROR = (
    "Adaptive learning could not be completed. "
    "Your quiz result was saved successfully."
)


class TestQuizResultSecurity:

    def setup_method(self):

        # -------------------------------------------------
        # 1. VERIFY ISOLATED TEST DATABASE
        # -------------------------------------------------

        verify_test_database()

        Base.metadata.create_all(bind=test_engine)

        # Preserve existing dependency overrides.
        self.original_dependency_overrides = (
            app.dependency_overrides.copy()
        )

        self.db = TestSessionLocal()

        # -------------------------------------------------
        # 2. CREATE TWO TEST STUDENTS
        # -------------------------------------------------

        unique_id = uuid.uuid4().hex[:12]

        self.student = Student(
            name="Quiz Security Student",
            email=f"quiz_student_{unique_id}@test.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
        )

        self.other_student = Student(
            name="Other Quiz Student",
            email=f"other_quiz_student_{unique_id}@test.com",
            daily_available_hours=3.0,
            learning_preference="Reading",
        )

        self.db.add_all(
            [
                self.student,
                self.other_student,
            ]
        )

        self.db.commit()

        self.db.refresh(self.student)
        self.db.refresh(self.other_student)

        self.student_id = self.student.student_id
        self.other_student_id = self.other_student.student_id

        # -------------------------------------------------
        # 3. CREATE SUBJECTS
        # -------------------------------------------------

        self.subject = Subject(
            student_id=self.student_id,
            subject_name="DBMS",
        )

        self.other_subject = Subject(
            student_id=self.other_student_id,
            subject_name="Python",
        )

        self.db.add_all(
            [
                self.subject,
                self.other_subject,
            ]
        )

        self.db.commit()

        self.db.refresh(self.subject)
        self.db.refresh(self.other_subject)

        # -------------------------------------------------
        # 4. CREATE TOPICS
        # -------------------------------------------------

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="Normalization",
            difficulty=3,
        )

        self.other_topic = Topic(
            subject_id=self.other_subject.subject_id,
            topic_name="Python OOP",
            difficulty=2,
        )

        self.db.add_all(
            [
                self.topic,
                self.other_topic,
            ]
        )

        self.db.commit()

        self.db.refresh(self.topic)
        self.db.refresh(self.other_topic)

        # -------------------------------------------------
        # 5. CREATE QUIZZES
        # -------------------------------------------------

        self.quiz = Quiz(
            topic_id=self.topic.topic_id,
            title="Normalization Quiz",
            difficulty=3,
        )

        self.other_quiz = Quiz(
            topic_id=self.other_topic.topic_id,
            title="Python OOP Quiz",
            difficulty=2,
        )

        self.db.add_all(
            [
                self.quiz,
                self.other_quiz,
            ]
        )

        self.db.commit()

        self.db.refresh(self.quiz)
        self.db.refresh(self.other_quiz)

        self.quiz_id = self.quiz.quiz_id
        self.other_quiz_id = self.other_quiz.quiz_id

        # -------------------------------------------------
        # 6. CREATE QUIZ QUESTIONS
        # -------------------------------------------------

        self.question = QuizQuestion(
            quiz_id=self.quiz_id,
            question_text="Which normal form removes partial dependencies?",
            option_a="First Normal Form",
            option_b="Second Normal Form",
            option_c="Third Normal Form",
            option_d="BCNF",
            correct_option="B",
            explanation="Second Normal Form removes partial dependencies.",
            points=1,
        )

        self.other_question = QuizQuestion(
            quiz_id=self.other_quiz_id,
            question_text="Which keyword defines a Python function?",
            option_a="func",
            option_b="define",
            option_c="def",
            option_d="function",
            correct_option="C",
            explanation="The def keyword defines a function.",
            points=1,
        )

        self.db.add_all(
            [
                self.question,
                self.other_question,
            ]
        )

        self.db.commit()

        self.db.refresh(self.question)
        self.db.refresh(self.other_question)

        self.question_id = self.question.question_id
        self.other_question_id = self.other_question.question_id

        # -------------------------------------------------
        # 7. OVERRIDE DATABASE DEPENDENCY
        # -------------------------------------------------

        def override_get_db():

            db = TestSessionLocal()

            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[
            quiz_result_routes.get_db
        ] = override_get_db

        # -------------------------------------------------
        # 8. OVERRIDE AUTHENTICATED STUDENT
        # -------------------------------------------------

        app.dependency_overrides[
            get_current_student
        ] = lambda: self.student

        self.client = TestClient(app)

    # =====================================================
    # CLEANUP
    # =====================================================

    def teardown_method(self):

        try:

            # Delete only records belonging to these test students.
            # Never delete unrelated student or historical records.

            result_ids = (
                self.db.query(QuizResult.result_id)
                .filter(
                    QuizResult.student_id.in_(
                        [
                            self.student_id,
                            self.other_student_id,
                        ]
                    )
                )
                .subquery()
            )

            self.db.query(QuizAnswer).filter(
                QuizAnswer.result_id.in_(
                    self.db.query(result_ids.c.result_id)
                )
            ).delete(synchronize_session=False)

            self.db.query(QuizResult).filter(
                QuizResult.student_id.in_(
                    [
                        self.student_id,
                        self.other_student_id,
                    ]
                )
            ).delete(synchronize_session=False)

            quiz_ids = [
                self.quiz_id,
                self.other_quiz_id,
            ]

            self.db.query(QuizQuestion).filter(
                QuizQuestion.quiz_id.in_(quiz_ids)
            ).delete(synchronize_session=False)

            self.db.query(Quiz).filter(
                Quiz.quiz_id.in_(quiz_ids)
            ).delete(synchronize_session=False)

            topic_ids = [
                self.topic.topic_id,
                self.other_topic.topic_id,
            ]

            self.db.query(Topic).filter(
                Topic.topic_id.in_(topic_ids)
            ).delete(synchronize_session=False)

            subject_ids = [
                self.subject.subject_id,
                self.other_subject.subject_id,
            ]

            self.db.query(Subject).filter(
                Subject.subject_id.in_(subject_ids)
            ).delete(synchronize_session=False)

            self.db.query(Student).filter(
                Student.student_id.in_(
                    [
                        self.student_id,
                        self.other_student_id,
                    ]
                )
            ).delete(synchronize_session=False)

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        finally:

            self.db.close()

            # Restore the dependency overrides that existed
            # before this test class was initialized.
            app.dependency_overrides.clear()
            app.dependency_overrides.update(
                self.original_dependency_overrides
            )

    # =====================================================
    # HELPER: VALID QUIZ SUBMISSION
    # =====================================================

    def valid_submission(self):

        return {
            "student_id": self.student_id,
            "answers": [
                {
                    "question_id": self.question_id,
                    "selected_option": "B",
                }
            ],
        }

    # =====================================================
    # TEST 1: CANNOT SUBMIT ANOTHER STUDENT'S QUIZ
    # =====================================================

    def test_cannot_submit_another_students_quiz(self):

        response = self.client.post(
            "/quiz-results/",
            params={
                "quiz_id": self.other_quiz_id,
            },
            json=self.valid_submission(),
        )

        assert response.status_code == 404

        assert response.json()["detail"] == "Quiz not found."

    # =====================================================
    # TEST 2: FOREIGN AND NONEXISTENT QUIZ SAME RESPONSE
    # =====================================================

    def test_foreign_and_nonexistent_quiz_return_same_response(self):

        foreign_response = self.client.post(
            "/quiz-results/",
            params={
                "quiz_id": self.other_quiz_id,
            },
            json=self.valid_submission(),
        )

        nonexistent_response = self.client.post(
            "/quiz-results/",
            params={
                "quiz_id": 999999999,
            },
            json=self.valid_submission(),
        )

        assert foreign_response.status_code == 404

        assert nonexistent_response.status_code == 404

        assert (
            foreign_response.json()["detail"]
            ==
            nonexistent_response.json()["detail"]
        )

    # =====================================================
    # TEST 3: WORKFLOW EXCEPTION DOES NOT EXPOSE INTERNAL ERROR
    # =====================================================

    def test_workflow_exception_does_not_expose_internal_error(
        self,
        monkeypatch,
    ):

        def failing_workflow(state):

            raise RuntimeError(
                "Internal workflow failure"
            )

        monkeypatch.setattr(
            quiz_result_routes.adaptive_workflow,
            "invoke",
            failing_workflow,
        )

        response = self.client.post(
            "/quiz-results/",
            params={
                "quiz_id": self.quiz_id,
            },
            json=self.valid_submission(),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["workflow_status"] == "failed"

        assert data["workflow_error"] == SAFE_WORKFLOW_ERROR

        assert "Internal workflow failure" not in str(data)

        assert data["errors"] == [
            SAFE_WORKFLOW_ERROR
        ]

    # =====================================================
    # TEST 4: NESTED AGENT ERRORS ARE SANITIZED
    # =====================================================

    def test_nested_agent_errors_are_sanitized(
        self,
        monkeypatch,
    ):

        def workflow_with_nested_errors(state):

            return {
                "evaluation": {
                    "score": 100,
                    "level": "strong",
                },
                "validation": {
                    "status": "failed",
                    "errors": [
                        "Internal database connection failure"
                    ],
                },
                "errors": [
                    "Internal agent exception"
                ],
            }

        monkeypatch.setattr(
            quiz_result_routes.adaptive_workflow,
            "invoke",
            workflow_with_nested_errors,
        )

        response = self.client.post(
            "/quiz-results/",
            params={
                "quiz_id": self.quiz_id,
            },
            json=self.valid_submission(),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["workflow_status"] == "completed_with_errors"

        assert data["errors"] == [
            SAFE_WORKFLOW_ERROR
        ]

        assert (
            data["validation"]["errors"]
            ==
            SAFE_WORKFLOW_ERROR
        )

        assert "Internal agent exception" not in str(data)

        assert (
            "Internal database connection failure"
            not in str(data)
        )

    # =====================================================
    # TEST 5: QUIZ RESULT MUST BE SAVED IF WORKFLOW FAILS
    # =====================================================

    def test_quiz_result_is_saved_when_workflow_fails(
        self,
        monkeypatch,
    ):

        def failing_workflow(state):

            raise RuntimeError(
                "Internal workflow failure"
            )

        monkeypatch.setattr(
            quiz_result_routes.adaptive_workflow,
            "invoke",
            failing_workflow,
        )

        response = self.client.post(
            "/quiz-results/",
            params={
                "quiz_id": self.quiz_id,
            },
            json=self.valid_submission(),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["workflow_status"] == "failed"

        assert data["workflow_error"] == SAFE_WORKFLOW_ERROR

        result_id = data["result_id"]

        # -------------------------------------------------
        # IMPORTANT:
        # Verify persistence using a completely new session.
        # Do not use the fixture session for this verification.
        # -------------------------------------------------

        verification_db = TestSessionLocal()

        try:

            saved_result = (
                verification_db.query(QuizResult)
                .filter(
                    QuizResult.result_id == result_id,
                    QuizResult.student_id == self.student_id,
                    QuizResult.quiz_id == self.quiz_id,
                )
                .first()
            )

            assert saved_result is not None

            assert saved_result.score == 100.0

            saved_answers = (
                verification_db.query(QuizAnswer)
                .filter(
                    QuizAnswer.result_id == result_id
                )
                .all()
            )

            assert len(saved_answers) == 1

            assert saved_answers[0].question_id == self.question_id

            assert saved_answers[0].selected_option == "B"

            assert saved_answers[0].is_correct is True

            assert saved_answers[0].points_awarded == 1

        finally:

            verification_db.close()

    # =====================================================
    # TEST 6: STUDENT CANNOT ACCESS ANOTHER STUDENT'S RESULTS
    # =====================================================

    def test_cannot_retrieve_another_students_results(self):

        response = self.client.get(
            f"/quiz-results/student/{self.other_student_id}"
        )

        assert response.status_code == 404

        assert response.json()["detail"] == "Student not found."

    # =====================================================
    # TEST 7: STUDENT CANNOT ACCESS ANOTHER STUDENT'S QUIZ RESULTS
    # =====================================================

    def test_cannot_retrieve_results_for_another_students_quiz(self):

        response = self.client.get(
            f"/quiz-results/quiz/{self.other_quiz_id}"
        )

        assert response.status_code == 404

        assert response.json()["detail"] == "Quiz not found."