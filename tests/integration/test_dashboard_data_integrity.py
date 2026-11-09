
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import dashboard_routes
from app.api.dependencies import get_current_student
from app.database.connection import Base
from app.database.models import (
    Performance,
    Student,
    StudyPlan,
    StudyPlanItem,
    Subject,
    Topic,
)
from app.main import app
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


class TestDashboardDataIntegrity:

    @classmethod
    def setup_class(cls):
        verify_test_database()
        Base.metadata.create_all(bind=test_engine)

    def setup_method(self):
        self.original_dependency_overrides = (
            app.dependency_overrides.copy()
        )

        app.dependency_overrides[
            dashboard_routes.get_db
        ] = override_get_db

        self.client = TestClient(app)
        self.db = TestSessionLocal()

        unique_id = uuid4().hex

        self.student = Student(
            name="Dashboard Test Student",
            email=f"dashboard_{unique_id}@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
        )

        self.other_student = Student(
            name="Other Dashboard Student",
            email=f"other_dashboard_{unique_id}@example.com",
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
            subject_name="Dashboard Test DBMS",
            importance=3,
        )

        self.other_subject = Subject(
            student_id=self.other_student.student_id,
            subject_name="Other Student DBMS",
            importance=3,
        )

        self.db.add_all([
            self.subject,
            self.other_subject,
        ])
        self.db.flush()

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="Owned Topic",
            difficulty=3,
        )

        self.other_topic = Topic(
            subject_id=self.other_subject.subject_id,
            topic_name="Foreign Topic",
            difficulty=3,
        )

        self.db.add_all([
            self.topic,
            self.other_topic,
        ])
        self.db.flush()

        now = datetime.now().replace(microsecond=0)

        self.active_plan = StudyPlan(
            student_id=self.student.student_id,
            start_date=now,
            end_date=now + timedelta(days=7),
            status="active",
        )

        self.inactive_plan = StudyPlan(
            student_id=self.student.student_id,
            start_date=now - timedelta(days=14),
            end_date=now - timedelta(days=7),
            status="superseded",
        )

        self.db.add_all([
            self.active_plan,
            self.inactive_plan,
        ])
        self.db.flush()

        self.valid_active_item = StudyPlanItem(
            plan_id=self.active_plan.plan_id,
            topic_id=self.topic.topic_id,
            scheduled_date=now + timedelta(days=1),
            duration_minutes=45,
            priority=1,
            status="pending",
        )

        self.db.add(self.valid_active_item)
        self.db.commit()

        self.student_id = self.student.student_id
        self.other_student_id = self.other_student.student_id

        self.subject_id = self.subject.subject_id
        self.other_subject_id = self.other_subject.subject_id

        self.topic_id = self.topic.topic_id
        self.other_topic_id = self.other_topic.topic_id

        self.active_plan_id = self.active_plan.plan_id
        self.inactive_plan_id = self.inactive_plan.plan_id

    def teardown_method(self):
        try:
            self.db.rollback()
            self.db.expire_all()

            plan_ids = [
                self.active_plan_id,
                self.inactive_plan_id,
            ]

            self.db.query(StudyPlanItem).filter(
                StudyPlanItem.plan_id.in_(plan_ids)
            ).delete(synchronize_session=False)

            self.db.query(StudyPlan).filter(
                StudyPlan.plan_id.in_(plan_ids)
            ).delete(synchronize_session=False)

            self.db.query(Performance).filter(
                Performance.student_id == self.student_id
            ).delete(synchronize_session=False)

            topic_ids = [
                self.topic_id,
                self.other_topic_id,
            ]

            self.db.query(Topic).filter(
                Topic.topic_id.in_(topic_ids)
            ).delete(synchronize_session=False)

            subject_ids = [
                self.subject_id,
                self.other_subject_id,
            ]

            self.db.query(Subject).filter(
                Subject.subject_id.in_(subject_ids)
            ).delete(synchronize_session=False)

            student_ids = [
                self.student_id,
                self.other_student_id,
            ]

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

    def get_dashboard(self):
        return self.client.get(
            f"/dashboard/student/{self.student_id}"
        )

    def test_foreign_topic_performance_does_not_affect_dashboard(
        self,
    ):
        self.db.add_all([
            Performance(
                student_id=self.student_id,
                topic_id=self.topic_id,
                score=80.0,
            ),
            Performance(
                student_id=self.student_id,
                topic_id=self.other_topic_id,
                score=10.0,
            ),
        ])
        self.db.commit()

        response = self.get_dashboard()

        assert response.status_code == 200

        body = response.json()

        assert body["average_score"] == 80.0
        assert body["weak_topics"] == 0
        assert body["moderate_topics"] == 0
        assert body["strong_topics"] == 1

    def test_foreign_topic_does_not_affect_active_session_counts(
        self,
    ):
        foreign_item = StudyPlanItem(
            plan_id=self.active_plan_id,
            topic_id=self.other_topic_id,
            scheduled_date=datetime.now() + timedelta(days=2),
            duration_minutes=60,
            priority=2,
            status="completed",
        )

        self.db.add(foreign_item)
        self.db.commit()

        response = self.get_dashboard()

        assert response.status_code == 200

        body = response.json()

        assert body["active_total_sessions"] == 1
        assert body["active_pending_sessions"] == 1
        assert body["active_completed_sessions"] == 0

    def test_foreign_topic_in_inactive_plan_does_not_affect_overall_counts(
        self,
    ):
        invalid_item = StudyPlanItem(
            plan_id=self.inactive_plan_id,
            topic_id=self.other_topic_id,
            scheduled_date=datetime.now() - timedelta(days=10),
            duration_minutes=60,
            priority=2,
            status="completed",
        )

        self.db.add(invalid_item)
        self.db.commit()

        response = self.get_dashboard()

        assert response.status_code == 200

        body = response.json()

        assert body["overall_completed_sessions"] == 0
        assert body["overall_pending_sessions"] == 1
        assert body["overall_in_progress_sessions"] == 0

    def test_valid_records_still_contribute_to_dashboard_statistics(
        self,
    ):
        completed_item = StudyPlanItem(
            plan_id=self.active_plan_id,
            topic_id=self.topic_id,
            scheduled_date=datetime.now() + timedelta(days=2),
            duration_minutes=60,
            priority=2,
            status="completed",
        )

        self.db.add_all([
            Performance(
                student_id=self.student_id,
                topic_id=self.topic_id,
                score=90.0,
            ),
            completed_item,
        ])
        self.db.commit()

        response = self.get_dashboard()

        assert response.status_code == 200

        body = response.json()

        assert body["total_subjects"] == 1
        assert body["total_topics"] == 1

        assert body["average_score"] == 90.0
        assert body["strong_topics"] == 1

        assert body["active_total_sessions"] == 2
        assert body["active_pending_sessions"] == 1
        assert body["active_completed_sessions"] == 1

        assert body["overall_pending_sessions"] == 1
        assert body["overall_completed_sessions"] == 1
