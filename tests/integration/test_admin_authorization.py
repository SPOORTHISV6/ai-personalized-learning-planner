
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import quiz_routes, resource_routes
from app.api.dependencies import get_current_student
from app.database.connection import Base
from app.database.models import (
    Quiz,
    QuizQuestion,
    Resource,
    Student,
    Subject,
    Topic,
)
from app.main import app

from tests.integration.test_database import (
    TestSessionLocal,
    test_engine,
    verify_test_database,
)


def override_get_test_db():
    """Use only the isolated MySQL integration-test database."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestAdminAuthorization:

    @classmethod
    def setup_class(cls):
        verify_test_database()
        Base.metadata.create_all(bind=test_engine)

    def setup_method(self):
        # Preserve dependency overrides used by other tests.
        self.original_dependency_overrides = (
            app.dependency_overrides.copy()
        )

        # Quiz and resource routes use different get_db functions.
        app.dependency_overrides[
            quiz_routes.get_db
        ] = override_get_test_db

        app.dependency_overrides[
            resource_routes.get_db
        ] = override_get_test_db

        self.client = TestClient(app)
        self.db = TestSessionLocal()

        unique_id = uuid4().hex

        # Create an ordinary student.
        self.student = Student(
            name="Authorization Test Student",
            email=f"student_{unique_id}@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
            role="student",
        )

        # Create a temporary administrator.
        self.admin = Student(
            name="Authorization Test Admin",
            email=f"admin_{unique_id}@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
            role="admin",
        )

        # Create another student to test ownership restrictions.
        self.other_student = Student(
            name="Other Authorization Student",
            email=f"other_{unique_id}@example.com",
            daily_available_hours=3.0,
            learning_preference="Reading",
            role="student",
        )

        self.db.add_all([
            self.student,
            self.admin,
            self.other_student,
        ])
        self.db.flush()

        # Create a subject and topic owned by the test student.
        self.subject = Subject(
            student_id=self.student.student_id,
            subject_name="Authorization Test DBMS",
            importance=3,
        )

        self.db.add(self.subject)
        self.db.flush()

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="Authorization Test Normalization",
            difficulty=3,
        )

        self.db.add(self.topic)
        self.db.flush()

        # Create another subject and topic owned by another student.
        self.other_subject = Subject(
            student_id=self.other_student.student_id,
            subject_name="Other Student DBMS",
            importance=2,
        )

        self.db.add(self.other_subject)
        self.db.flush()

        self.other_topic = Topic(
            subject_id=self.other_subject.subject_id,
            topic_name="Other Student SQL Joins",
            difficulty=2,
        )

        self.db.add(self.other_topic)
        self.db.commit()

        self.student_id = self.student.student_id
        self.admin_id = self.admin.student_id
        self.other_student_id = self.other_student.student_id

        self.topic_id = self.topic.topic_id
        self.other_topic_id = self.other_topic.topic_id

        # Default authenticated identity is the ordinary student.
        self.current_student = self.student

        app.dependency_overrides[get_current_student] = (
            lambda: self.current_student
        )

    def authenticate_as(self, student):
        """Switch the authenticated test identity."""
        self.current_student = student

    def create_quiz_directly(self, topic_id=None):
        """Create a quiz fixture directly in the test database."""
        quiz = Quiz(
            topic_id=topic_id or self.topic_id,
            title="Authorization Test Quiz",
            difficulty=3,
        )

        self.db.add(quiz)
        self.db.commit()
        self.db.refresh(quiz)

        return quiz

    def create_resource_as_admin(self, topic_id=None):
        """Create a resource through the administrator API."""
        self.authenticate_as(self.admin)

        response = self.client.post(
            "/resources/",
            json={
                "topic_id": topic_id or self.topic_id,
                "title": "Authorization Test Resource",
                "resource_type": "PDF",
                "source": "Integration Test",
                "content_path": "test/authorization.pdf",
            },
        )

        assert response.status_code == 201, response.text
        return response.json()

    def teardown_method(self):
        """Delete only records created by this test."""

        try:
            self.db.rollback()
            self.db.expire_all()

            topic_ids = [
                self.topic_id,
                self.other_topic_id,
            ]

            # Find quizzes associated with test topics.
            quiz_ids = [
                row[0]
                for row in (
                    self.db.query(Quiz.quiz_id)
                    .filter(Quiz.topic_id.in_(topic_ids))
                    .all()
                )
            ]

            if quiz_ids:
                # Delete questions before their parent quizzes.
                self.db.query(QuizQuestion).filter(
                    QuizQuestion.quiz_id.in_(quiz_ids)
                ).delete(synchronize_session=False)

                self.db.query(Quiz).filter(
                    Quiz.quiz_id.in_(quiz_ids)
                ).delete(synchronize_session=False)

            # Delete resources belonging to test topics.
            self.db.query(Resource).filter(
                Resource.topic_id.in_(topic_ids)
            ).delete(synchronize_session=False)

            # Remove topic records.
            self.db.query(Topic).filter(
                Topic.topic_id.in_(topic_ids)
            ).update(
                {Topic.prerequisite_topic_id: None},
                synchronize_session=False,
            )

            self.db.query(Topic).filter(
                Topic.topic_id.in_(topic_ids)
            ).delete(synchronize_session=False)

            # Remove test subjects.
            subject_ids = [
                self.subject.subject_id,
                self.other_subject.subject_id,
            ]

            self.db.query(Subject).filter(
                Subject.subject_id.in_(subject_ids)
            ).delete(synchronize_session=False)

            # Remove only the three temporary test students.
            student_ids = [
                self.student_id,
                self.admin_id,
                self.other_student_id,
            ]

            self.db.query(Student).filter(
                Student.student_id.in_(student_ids)
            ).delete(synchronize_session=False)

            self.db.commit()

        finally:
            self.db.close()

            # Restore all previous dependency overrides.
            app.dependency_overrides.clear()
            app.dependency_overrides.update(
                self.original_dependency_overrides
            )

    # --------------------------------------------------------
    # QUIZ AUTHORIZATION
    # --------------------------------------------------------

    def test_student_cannot_create_quiz(self):
        self.authenticate_as(self.student)

        response = self.client.post(
            "/quizzes/",
            json={
                "topic_id": self.topic_id,
                "title": "Student Created Quiz",
                "difficulty": 3,
            },
        )

        assert response.status_code == 403

    def test_admin_can_create_quiz(self):
        self.authenticate_as(self.admin)

        response = self.client.post(
            "/quizzes/",
            json={
                "topic_id": self.topic_id,
                "title": "Admin Created Quiz",
                "difficulty": 4,
            },
        )

        assert response.status_code == 201
        assert response.json()["title"] == "Admin Created Quiz"
        assert response.json()["topic_id"] == self.topic_id

    def test_student_cannot_add_quiz_question(self):
        quiz = self.create_quiz_directly()

        self.authenticate_as(self.student)

        response = self.client.post(
            f"/quizzes/{quiz.quiz_id}/questions",
            json={
                "question_text": "What is normalization?",
                "option_a": "Data organization",
                "option_b": "Data deletion",
                "option_c": "Data duplication",
                "option_d": "Data encryption",
                "correct_option": "A",
                "explanation": "Normalization organizes relational data.",
                "points": 1,
            },
        )

        assert response.status_code == 403

    def test_admin_can_add_quiz_question(self):
        quiz = self.create_quiz_directly()

        self.authenticate_as(self.admin)

        response = self.client.post(
            f"/quizzes/{quiz.quiz_id}/questions",
            json={
                "question_text": "What is normalization?",
                "option_a": "Data organization",
                "option_b": "Data deletion",
                "option_c": "Data duplication",
                "option_d": "Data encryption",
                "correct_option": "A",
                "explanation": "Normalization organizes relational data.",
                "points": 2,
            },
        )

        assert response.status_code == 201
        assert response.json()["correct_option"] == "A"

    # --------------------------------------------------------
    # QUIZ ANSWER-KEY PROTECTION
    # --------------------------------------------------------

    def test_student_cannot_view_correct_option(self):
        quiz = self.create_quiz_directly()

        question = QuizQuestion(
            quiz_id=quiz.quiz_id,
            question_text="What is normalization?",
            option_a="Data organization",
            option_b="Data deletion",
            option_c="Data duplication",
            option_d="Data encryption",
            correct_option="A",
            explanation="Normalization organizes relational data.",
            points=1,
        )

        self.db.add(question)
        self.db.commit()

        self.authenticate_as(self.student)

        response = self.client.get(
            f"/quizzes/{quiz.quiz_id}/questions"
        )

        assert response.status_code == 200
        assert len(response.json()) == 1

        question_response = response.json()[0]

        assert "correct_option" not in question_response
        assert question_response["question_text"] == (
            "What is normalization?"
        )

    def test_student_cannot_access_another_students_quiz(self):
        self.authenticate_as(self.admin)

        create_response = self.client.post(
            "/quizzes/",
            json={
                "topic_id": self.other_topic_id,
                "title": "Other Student Quiz",
                "difficulty": 2,
            },
        )

        assert create_response.status_code == 201

        quiz_id = create_response.json()["quiz_id"]

        self.authenticate_as(self.student)

        response = self.client.get(
            f"/quizzes/{quiz_id}"
        )

        assert response.status_code == 404

    # --------------------------------------------------------
    # RESOURCE AUTHORIZATION
    # --------------------------------------------------------

    def test_student_cannot_create_resource(self):
        self.authenticate_as(self.student)

        response = self.client.post(
            "/resources/",
            json={
                "topic_id": self.topic_id,
                "title": "Student Created Resource",
                "resource_type": "PDF",
                "source": "Integration Test",
                "content_path": "test/student.pdf",
            },
        )

        assert response.status_code == 403

    def test_admin_can_create_resource(self):
        self.authenticate_as(self.admin)

        response = self.client.post(
            "/resources/",
            json={
                "topic_id": self.topic_id,
                "title": "Admin Created Resource",
                "resource_type": "PDF",
                "source": "Integration Test",
                "content_path": "test/admin.pdf",
            },
        )

        assert response.status_code == 201
        assert response.json()["title"] == "Admin Created Resource"
        assert response.json()["topic_id"] == self.topic_id

    def test_student_can_read_own_topic_resource(self):
        resource = self.create_resource_as_admin()

        self.authenticate_as(self.student)

        response = self.client.get(
            f"/resources/{resource['resource_id']}"
        )

        assert response.status_code == 200
        assert response.json()["title"] == (
            "Authorization Test Resource"
        )

    def test_student_cannot_read_another_students_resource(self):
        resource = self.create_resource_as_admin(
            topic_id=self.other_topic_id
        )

        self.authenticate_as(self.student)

        response = self.client.get(
            f"/resources/{resource['resource_id']}"
        )

        assert response.status_code == 404

    def test_student_cannot_read_another_students_topic_resources(self):
        self.authenticate_as(self.admin)

        create_response = self.client.post(
            "/resources/",
            json={
                "topic_id": self.other_topic_id,
                "title": "Other Student Resource",
                "resource_type": "PDF",
                "source": "Integration Test",
                "content_path": "test/other.pdf",
            },
        )

        assert create_response.status_code == 201

        self.authenticate_as(self.student)

        response = self.client.get(
            f"/resources/topic/{self.other_topic_id}"
        )

        assert response.status_code == 404
