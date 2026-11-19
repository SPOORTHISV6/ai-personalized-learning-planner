

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import learning_gap_routes
from app.api.dependencies import get_current_student
from app.database.connection import Base
from app.database.models import (
    Performance,
    Student,
    Subject,
    Topic,
)
from app.main import app
from app.tools.learning_gap import calculate_learning_gaps
from tests.integration.test_database import (
    TestSessionLocal,
    test_engine,
    verify_test_database,
)


def override_get_db():
    """Use the isolated integration-test database."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestLearningGapSecurity:

    @classmethod
    def setup_class(cls):
        verify_test_database()
        Base.metadata.create_all(bind=test_engine)

    def setup_method(self):
        self.original_dependency_overrides = (
            app.dependency_overrides.copy()
        )

        app.dependency_overrides[
            learning_gap_routes.get_db
        ] = override_get_db

        self.client = TestClient(app)
        self.db = TestSessionLocal()

        unique_id = uuid4().hex

        self.student = Student(
            name="Learning Gap Test Student",
            email=f"learning_gap_{unique_id}@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
        )

        self.other_student = Student(
            name="Other Learning Gap Student",
            email=f"other_learning_gap_{unique_id}@example.com",
            daily_available_hours=3.0,
            learning_preference="Reading",
        )

        self.db.add_all([
            self.student,
            self.other_student,
        ])
        self.db.flush()

        app.dependency_overrides[get_current_student] = (
            lambda: self.student
        )

        self.subject = Subject(
            student_id=self.student.student_id,
            subject_name="Learning Gap DBMS",
            importance=3,
        )

        self.other_subject = Subject(
            student_id=self.other_student.student_id,
            subject_name="Other Learning Gap DBMS",
            importance=3,
        )

        self.db.add_all([
            self.subject,
            self.other_subject,
        ])
        self.db.flush()

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="Owned Normalization",
            difficulty=3,
        )

        self.other_topic = Topic(
            subject_id=self.other_subject.subject_id,
            topic_name="Foreign Normalization",
            difficulty=3,
        )

        self.db.add_all([
            self.topic,
            self.other_topic,
        ])
        self.db.flush()

        self.student_id = self.student.student_id
        self.other_student_id = self.other_student.student_id

        self.subject_id = self.subject.subject_id
        self.other_subject_id = self.other_subject.subject_id

        self.topic_id = self.topic.topic_id
        self.other_topic_id = self.other_topic.topic_id

    def teardown_method(self):
        try:
            self.db.rollback()
            self.db.expire_all()

            student_ids = [
                self.student_id,
                self.other_student_id,
            ]

            topic_ids = [
                self.topic_id,
                self.other_topic_id,
            ]

            subject_ids = [
                self.subject_id,
                self.other_subject_id,
            ]

            self.db.query(Performance).filter(
                Performance.student_id.in_(student_ids)
            ).delete(synchronize_session=False)

            self.db.query(Topic).filter(
                Topic.topic_id.in_(topic_ids)
            ).delete(synchronize_session=False)

            self.db.query(Subject).filter(
                Subject.subject_id.in_(subject_ids)
            ).delete(synchronize_session=False)

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

    def add_performance(
        self,
        student_id,
        topic_id,
        score,
        attempt_date,
    ):
        performance = Performance(
            student_id=student_id,
            topic_id=topic_id,
            score=score,
            attempt_date=attempt_date,
        )

        self.db.add(performance)
        self.db.flush()

        return performance

    def test_student_sees_only_owned_learning_gaps(self):
        now = datetime.now()

        self.add_performance(
            self.student_id,
            self.topic_id,
            45.0,
            now,
        )

        self.add_performance(
            self.other_student_id,
            self.other_topic_id,
            30.0,
            now,
        )

        self.db.commit()

        gaps = calculate_learning_gaps(
            self.student_id,
            self.db,
        )

        assert len(gaps) == 1
        assert gaps[0]["topic_id"] == self.topic_id
        assert gaps[0]["topic_name"] == "Owned Normalization"

    def test_foreign_topic_is_excluded_even_with_own_performance(self):
        now = datetime.now()

        # Deliberately create an inconsistent record:
        # the performance belongs to this student,
        # but the topic belongs to another student.
        self.add_performance(
            self.student_id,
            self.other_topic_id,
            35.0,
            now,
        )

        self.db.commit()

        gaps = calculate_learning_gaps(
            self.student_id,
            self.db,
        )

        assert gaps == []

    def test_foreign_performance_is_excluded(self):
        now = datetime.now()

        # The topic belongs to this student,
        # but the performance belongs to another student.
        self.add_performance(
            self.other_student_id,
            self.topic_id,
            35.0,
            now,
        )

        self.db.commit()

        gaps = calculate_learning_gaps(
            self.student_id,
            self.db,
        )

        assert gaps == []

    def test_only_latest_attempt_is_selected(self):
        now = datetime.now()

        self.add_performance(
            self.student_id,
            self.topic_id,
            35.0,
            now - timedelta(days=2),
        )

        self.add_performance(
            self.student_id,
            self.topic_id,
            85.0,
            now,
        )

        self.db.commit()

        gaps = calculate_learning_gaps(
            self.student_id,
            self.db,
        )

        assert len(gaps) == 1
        assert gaps[0]["score"] == 85.0
        assert gaps[0]["status"] == "strong"
        assert gaps[0]["priority"] == "low"

    def test_duplicate_latest_timestamp_returns_one_gap(self):
        now = datetime.now()

        self.add_performance(
            self.student_id,
            self.topic_id,
            40.0,
            now,
        )

        latest_performance = self.add_performance(
            self.student_id,
            self.topic_id,
            80.0,
            now,
        )

        self.db.commit()

        gaps = calculate_learning_gaps(
            self.student_id,
            self.db,
        )

        assert len(gaps) == 1
        assert gaps[0]["score"] == 80.0
        assert gaps[0]["status"] == "strong"

        # Highest performance_id wins when timestamps match.
        assert latest_performance.performance_id is not None

    def test_student_cannot_access_another_students_learning_gaps(self):
        response = self.client.get(
            f"/learning-gaps/student/{self.other_student_id}"
        )

        assert response.status_code == 404

    def test_student_can_access_own_learning_gaps(self):
        now = datetime.now()

        self.add_performance(
            self.student_id,
            self.topic_id,
            45.0,
            now,
        )

        self.db.commit()

        response = self.client.get(
            f"/learning-gaps/student/{self.student_id}"
        )

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["topic_id"] == self.topic_id

    def test_unauthenticated_user_cannot_access_learning_gaps(self):
        app.dependency_overrides.pop(
            get_current_student,
            None,
        )

        response = self.client.get(
            f"/learning-gaps/student/{self.student_id}"
        )

        assert response.status_code == 401
