
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import subject_routes, topic_routes
from app.api.dependencies import get_current_student
from app.database.connection import Base
from app.database.models import Student, Subject, Topic
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


class TestSubjectTopicRoutes:

    @classmethod
    def setup_class(cls):
        verify_test_database()
        Base.metadata.create_all(bind=test_engine)

    def setup_method(self):
        self.original_dependency_overrides = (
            app.dependency_overrides.copy()
        )

        app.dependency_overrides[
            subject_routes.get_db
        ] = override_get_test_db

        app.dependency_overrides[
            topic_routes.get_db
        ] = override_get_test_db

        self.client = TestClient(app)
        self.db = TestSessionLocal()

        unique_id = uuid4().hex

        self.student = Student(
            name="Subject Topic Test Student",
            email=f"subject_topic_{unique_id}@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
            role="student",
        )

        self.other_student = Student(
            name="Other Subject Topic Student",
            email=f"other_subject_topic_{unique_id}@example.com",
            daily_available_hours=3.0,
            learning_preference="Reading",
            role="student",
        )

        self.db.add_all([
            self.student,
            self.other_student,
        ])
        self.db.flush()

        self.subject = Subject(
            student_id=self.student.student_id,
            subject_name="Test DBMS",
            importance=3,
        )

        self.other_subject = Subject(
            student_id=self.other_student.student_id,
            subject_name="Other Test DBMS",
            importance=2,
        )

        self.db.add_all([
            self.subject,
            self.other_subject,
        ])
        self.db.flush()

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="Test SQL Basics",
            difficulty=2,
        )

        self.other_topic = Topic(
            subject_id=self.other_subject.subject_id,
            topic_name="Other Test SQL Joins",
            difficulty=3,
        )

        self.db.add_all([
            self.topic,
            self.other_topic,
        ])
        self.db.commit()

        self.student_id = self.student.student_id
        self.other_student_id = self.other_student.student_id

        self.subject_id = self.subject.subject_id
        self.other_subject_id = self.other_subject.subject_id

        self.topic_id = self.topic.topic_id
        self.other_topic_id = self.other_topic.topic_id

        self.current_student = self.student

        app.dependency_overrides[get_current_student] = (
            lambda: self.current_student
        )

    def authenticate_as(self, student):
        self.current_student = student



    def teardown_method(self):
        try:
            self.db.rollback()
            self.db.expire_all()

            student_ids = [
                self.student_id,
                self.other_student_id,
            ]

            # Find every subject created for these test students,
            # including subjects created during individual tests.
            subject_ids = [
                row[0]
                for row in (
                    self.db.query(Subject.subject_id)
                    .filter(
                        Subject.student_id.in_(student_ids)
                    )
                    .all()
                )
            ]

            if subject_ids:
                # Find every topic belonging to these subjects.
                topic_ids = [
                    row[0]
                    for row in (
                        self.db.query(Topic.topic_id)
                        .filter(
                            Topic.subject_id.in_(subject_ids)
                        )
                        .all()
                    )
                ]

                if topic_ids:
                    # Clear self-referencing prerequisite links.
                    self.db.query(Topic).filter(
                        Topic.topic_id.in_(topic_ids)
                    ).update(
                        {Topic.prerequisite_topic_id: None},
                        synchronize_session=False,
                    )

                    # Delete only topics belonging to test subjects.
                    self.db.query(Topic).filter(
                        Topic.topic_id.in_(topic_ids)
                    ).delete(synchronize_session=False)

                # Delete all subjects belonging to test students.
                self.db.query(Subject).filter(
                    Subject.subject_id.in_(subject_ids)
                ).delete(synchronize_session=False)

            # Delete only the temporary test students.
            self.db.query(Student).filter(
                Student.student_id.in_(student_ids)
            ).delete(synchronize_session=False)

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        finally:
            self.db.close()
            self.client.close()

            app.dependency_overrides.clear()
            app.dependency_overrides.update(
                self.original_dependency_overrides
            )


    # ========================================================
    # SUBJECT ROUTE TESTS
    # ========================================================

    def test_student_can_create_own_subject(self):
        response = self.client.post(
            "/subjects/",
            json={
                "student_id": self.student_id,
                "subject_name": "Operating Systems",
                "importance": 4,
            },
        )

        assert response.status_code == 201, response.text

        data = response.json()

        assert data["student_id"] == self.student_id
        assert data["subject_name"] == "Operating Systems"
        assert data["importance"] == 4

    def test_student_cannot_create_subject_for_another_student(self):
        response = self.client.post(
            "/subjects/",
            json={
                "student_id": self.other_student_id,
                "subject_name": "Unauthorized Subject",
                "importance": 3,
            },
        )

        assert response.status_code == 403

    def test_student_can_list_own_subjects(self):
        response = self.client.get("/subjects/")

        assert response.status_code == 200

        data = response.json()

        assert any(
            subject["subject_id"] == self.subject_id
            for subject in data
        )

        assert all(
            subject["student_id"] == self.student_id
            for subject in data
        )

    def test_student_can_get_subjects_using_own_student_id(self):
        response = self.client.get(
            f"/subjects/student/{self.student_id}"
        )

        assert response.status_code == 200

        assert all(
            subject["student_id"] == self.student_id
            for subject in response.json()
        )

    def test_student_cannot_get_another_students_subjects(self):
        response = self.client.get(
            f"/subjects/student/{self.other_student_id}"
        )

        assert response.status_code == 404

    def test_subject_creation_rejects_invalid_importance(self):
        response = self.client.post(
            "/subjects/",
            json={
                "student_id": self.student_id,
                "subject_name": "Invalid Importance",
                "importance": 6,
            },
        )

        assert response.status_code == 422

    # ========================================================
    # TOPIC ROUTE TESTS
    # ========================================================

    def test_student_can_create_topic_in_own_subject(self):
        response = self.client.post(
            "/topics/",
            json={
                "subject_id": self.subject_id,
                "topic_name": "Database Normalization",
                "difficulty": 4,
            },
        )

        assert response.status_code == 201, response.text

        data = response.json()

        assert data["subject_id"] == self.subject_id
        assert data["topic_name"] == "Database Normalization"
        assert data["difficulty"] == 4

    def test_student_cannot_create_topic_in_another_students_subject(self):
        response = self.client.post(
            "/topics/",
            json={
                "subject_id": self.other_subject_id,
                "topic_name": "Unauthorized Topic",
                "difficulty": 3,
            },
        )

        assert response.status_code == 404

    def test_student_cannot_use_prerequisite_from_another_subject(self):
        response = self.client.post(
            "/topics/",
            json={
                "subject_id": self.subject_id,
                "topic_name": "Unauthorized Prerequisite Topic",
                "difficulty": 3,
                "prerequisite_topic_id": self.other_topic_id,
            },
        )

        assert response.status_code == 404

    def test_student_can_create_topic_with_own_prerequisite(self):
        response = self.client.post(
            "/topics/",
            json={
                "subject_id": self.subject_id,
                "topic_name": "SQL Joins",
                "difficulty": 3,
                "prerequisite_topic_id": self.topic_id,
            },
        )

        assert response.status_code == 201, response.text

        data = response.json()

        assert data["subject_id"] == self.subject_id
        assert data["prerequisite_topic_id"] == self.topic_id

    def test_student_can_list_own_topics(self):
        response = self.client.get("/topics/")

        assert response.status_code == 200

        data = response.json()

        assert any(
            topic["topic_id"] == self.topic_id
            for topic in data
        )

        assert all(
            topic["subject_id"] != self.other_subject_id
            for topic in data
        )

    def test_student_can_list_topics_for_own_subject(self):
        response = self.client.get(
            f"/topics/subject/{self.subject_id}"
        )

        assert response.status_code == 200

        data = response.json()

        assert all(
            topic["subject_id"] == self.subject_id
            for topic in data
        )

    def test_student_cannot_list_topics_for_another_students_subject(self):
        response = self.client.get(
            f"/topics/subject/{self.other_subject_id}"
        )

        assert response.status_code == 404

    def test_topic_creation_rejects_invalid_difficulty(self):
        response = self.client.post(
            "/topics/",
            json={
                "subject_id": self.subject_id,
                "topic_name": "Invalid Difficulty",
                "difficulty": 0,
            },
        )

        assert response.status_code == 422

    # ========================================================
    # AUTHENTICATION TESTS
    # ========================================================

    def test_subject_endpoint_rejects_unauthenticated_request(self):
        app.dependency_overrides.pop(
            get_current_student,
            None,
        )

        response = self.client.get("/subjects/")

        assert response.status_code == 401

    def test_topic_endpoint_rejects_unauthenticated_request(self):
        app.dependency_overrides.pop(
            get_current_student,
            None,
        )

        response = self.client.get("/topics/")

        assert response.status_code == 401
