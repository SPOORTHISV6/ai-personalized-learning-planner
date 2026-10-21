from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import (
    auth_routes,
    performance_routes,
    student_routes,
    study_plan_item_routes,
    study_plan_routes,
)
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
    """Use the isolated integration-test database for API requests."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestAPIRoutes:
    @classmethod
    def setup_class(cls):
        verify_test_database()
        Base.metadata.create_all(bind=test_engine)

    def setup_method(self):
        # Preserve dependency overrides configured by other tests.
        self.original_dependency_overrides = (
            app.dependency_overrides.copy()
        )

        # Route database operations to the isolated test database.
        app.dependency_overrides[
            auth_routes.get_db
        ] = override_get_db

        app.dependency_overrides[
            student_routes.get_db
        ] = override_get_db

        app.dependency_overrides[
            performance_routes.get_db
        ] = override_get_db

        app.dependency_overrides[
            study_plan_routes.get_db
        ] = override_get_db

        app.dependency_overrides[
            study_plan_item_routes.get_db
        ] = override_get_db

        self.client = TestClient(app)
        self.db = TestSessionLocal()

        self.email = f"api_test_{uuid4().hex}@example.com"

        self.student = Student(
            name="API Integration Student",
            email=self.email,
            daily_available_hours=4.0,
            learning_preference="Practice",
        )

        self.db.add(self.student)
        self.db.flush()

        # Authenticate API requests as the test student.
        app.dependency_overrides[get_current_student] = (
            lambda: self.student
        )

        self.subject = Subject(
            student_id=self.student.student_id,
            subject_name="API Test DBMS",
            importance=3,
        )

        self.db.add(self.subject)
        self.db.flush()

        self.topic = Topic(
            subject_id=self.subject.subject_id,
            topic_name="API Test Normalization",
            difficulty=3,
        )

        self.db.add(self.topic)
        self.db.flush()

        now = datetime.now().replace(microsecond=0)

        self.plan = StudyPlan(
            student_id=self.student.student_id,
            start_date=now,
            end_date=now + timedelta(days=7),
            status="active",
        )

        self.db.add(self.plan)
        self.db.flush()

        self.item = StudyPlanItem(
            plan_id=self.plan.plan_id,
            topic_id=self.topic.topic_id,
            scheduled_date=now + timedelta(days=1),
            duration_minutes=45,
            priority=1,
            status="pending",
        )

        self.db.add(self.item)
        self.db.commit()

        self.student_id = self.student.student_id
        self.plan_id = self.plan.plan_id
        self.topic_id = self.topic.topic_id
        self.item_id = self.item.item_id

    def teardown_method(self):
        """Remove test records in foreign-key dependency order."""
        try:
            self.db.rollback()
            self.db.expire_all()

            # Find all plans created for this test student.
            plan_ids = [
                row[0]
                for row in (
                    self.db.query(StudyPlan.plan_id)
                    .filter(
                        StudyPlan.student_id == self.student_id
                    )
                    .all()
                )
            ]

            # Delete plan items before their parent plans.
            if plan_ids:
                self.db.query(StudyPlanItem).filter(
                    StudyPlanItem.plan_id.in_(plan_ids)
                ).delete(synchronize_session=False)

                self.db.query(StudyPlan).filter(
                    StudyPlan.plan_id.in_(plan_ids)
                ).delete(synchronize_session=False)

            # Find subjects belonging to this student.
            subject_ids = [
                row[0]
                for row in (
                    self.db.query(Subject.subject_id)
                    .filter(
                        Subject.student_id == self.student_id
                    )
                    .all()
                )
            ]

            # Find topics belonging to this student's subjects.
            topic_ids = []
            if subject_ids:
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

            # Delete performance records before deleting topics
            # or the student because they reference both.
            self.db.query(Performance).filter(
                Performance.student_id == self.student_id
            ).delete(synchronize_session=False)

            # Delete topics before their parent subjects.
            if topic_ids:
                self.db.query(Topic).filter(
                    Topic.topic_id.in_(topic_ids)
                ).delete(synchronize_session=False)

            if subject_ids:
                self.db.query(Subject).filter(
                    Subject.subject_id.in_(subject_ids)
                ).delete(synchronize_session=False)

            # Remove the main test student.
            self.db.query(Student).filter(
                Student.student_id == self.student_id
            ).delete(synchronize_session=False)

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        finally:
            self.db.close()
            self.client.close()

            # Restore dependency overrides from before this test.
            app.dependency_overrides.clear()
            app.dependency_overrides.update(
                self.original_dependency_overrides
            )

    # ---------------------------------------------------------
    # ROOT ENDPOINT
    # ---------------------------------------------------------

    def test_root_endpoint(self):
        response = self.client.get("/")

        assert response.status_code == 200
        assert response.json()["message"] == (
            "AI Personalized Learning Planner is running"
        )

    # ---------------------------------------------------------
    # AUTHENTICATION AND REGISTRATION
    # ---------------------------------------------------------

    def test_create_student(self):
        email = f"new_student_{uuid4().hex}@example.com"

        response = self.client.post(
            "/auth/register",
            json={
                "name": "New API Student",
                "email": email,
                "password": "TestPassword123!",
                "daily_available_hours": 3.0,
                "learning_preference": "Reading",
            },
        )

        assert response.status_code == 201

        body = response.json()
        assert body["name"] == "New API Student"
        assert body["email"] == email
        assert body["student_id"] is not None
        assert "password_hash" not in body
        assert "password" not in body

        # Remove the extra student created by registration.
        self.db.rollback()

        self.db.query(Student).filter(
            Student.email == email
        ).delete(synchronize_session=False)

        self.db.commit()

    def test_duplicate_student_email_is_rejected(self):
        response = self.client.post(
            "/auth/register",
            json={
                "name": "Duplicate Student",
                "email": self.email,
                "password": "TestPassword123!",
                "daily_available_hours": 2.0,
                "learning_preference": "Practice",
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_get_my_profile(self):
        response = self.client.get("/students/me")

        assert response.status_code == 200
        assert response.json()["student_id"] == self.student_id
        assert response.json()["email"] == self.email

    def test_get_student(self):
        response = self.client.get(
            f"/students/{self.student_id}"
        )

        assert response.status_code == 200
        assert response.json()["student_id"] == self.student_id
        assert response.json()["email"] == self.email

    def test_missing_student_returns_404(self):
        response = self.client.get("/students/999999999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"

    def test_cannot_access_another_students_profile(self):
        other_student = Student(
            name="Another API Student",
            email=f"other_{uuid4().hex}@example.com",
            daily_available_hours=2.0,
            learning_preference="Practice",
        )

        self.db.add(other_student)
        self.db.commit()
        self.db.refresh(other_student)

        other_student_id = other_student.student_id

        try:
            response = self.client.get(
                f"/students/{other_student_id}"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Student not found"

        finally:
            self.db.rollback()

            self.db.query(Student).filter(
                Student.student_id == other_student_id
            ).delete(synchronize_session=False)

            self.db.commit()

    # ---------------------------------------------------------
    # PERFORMANCE ENDPOINTS
    # ---------------------------------------------------------

    def test_create_performance(self):
        response = self.client.post(
            "/performance/",
            json={
                "student_id": self.student_id,
                "topic_id": self.topic_id,
                "score": 85.0,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["performance_id"] is not None
        assert body["student_id"] == self.student_id
        assert body["topic_id"] == self.topic_id
        assert body["score"] == 85.0

        # Verify the committed record using a fresh database session.
        verification_db = TestSessionLocal()

        try:
            record = (
                verification_db.query(Performance)
                .filter(
                    Performance.performance_id
                    == body["performance_id"]
                )
                .one()
            )

            assert record.student_id == self.student_id
            assert record.topic_id == self.topic_id
            assert record.score == 85.0

            # Manual performance entries are not quiz-linked.
            assert record.quiz_result_id is None

        finally:
            verification_db.close()
    
    def test_create_performance_rejects_negative_score(self):
        response = self.client.post(
            "/performance/",
            json={
                "student_id": self.student_id,
                "topic_id": self.topic_id,
                "score": -1,
            },
        )

        assert response.status_code == 422

    def test_create_performance_rejects_score_above_100(self):
        response = self.client.post(
            "/performance/",
            json={
                "student_id": self.student_id,
                "topic_id": self.topic_id,
                "score": 101,
            },
        )

        assert response.status_code == 422

    def test_create_performance_accepts_zero_score(self):
        response = self.client.post(
            "/performance/",
            json={
                "student_id": self.student_id,
                "topic_id": self.topic_id,
                "score": 0,
            },
        )

        assert response.status_code == 200
        assert response.json()["score"] == 0.0

    def test_create_performance_accepts_100_score(self):
        response = self.client.post(
            "/performance/",
            json={
                "student_id": self.student_id,
                "topic_id": self.topic_id,
                "score": 100,
            },
        )

        assert response.status_code == 200
        assert response.json()["score"] == 100.0

    def test_create_performance_for_another_student_is_rejected(
        self,
    ):
        response = self.client.post(
            "/performance/",
            json={
                "student_id": self.student_id + 999999,
                "topic_id": self.topic_id,
                "score": 85.0,
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "You cannot create performance records "
            "for another student."
        )

    def test_create_performance_for_unknown_topic_is_rejected(
        self,
    ):
        response = self.client.post(
            "/performance/",
            json={
                "student_id": self.student_id,
                "topic_id": 999999999,
                "score": 85.0,
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Topic not found."

    def test_get_student_performance(self):
        self.db.add(
            Performance(
                student_id=self.student_id,
                topic_id=self.topic_id,
                score=75.0,
            )
        )
        self.db.commit()

        response = self.client.get(
            f"/performance/student/{self.student_id}"
        )

        assert response.status_code == 200

        records = response.json()

        assert any(
            record["student_id"] == self.student_id
            and record["topic_id"] == self.topic_id
            and record["score"] == 75.0
            for record in records
        )

    def test_cannot_access_another_students_performance(self):
        response = self.client.get(
            f"/performance/student/{self.student_id + 999999}"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found."

    def test_get_topic_performance(self):
        self.db.add(
            Performance(
                student_id=self.student_id,
                topic_id=self.topic_id,
                score=82.0,
            )
        )
        self.db.commit()

        response = self.client.get(
            f"/performance/topic/{self.topic_id}"
        )

        assert response.status_code == 200

        records = response.json()

        assert any(
            record["student_id"] == self.student_id
            and record["topic_id"] == self.topic_id
            and record["score"] == 82.0
            for record in records
        )

    def test_get_performance_for_unknown_topic_is_rejected(self):
        response = self.client.get(
            "/performance/topic/999999999"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Topic not found."

    # ---------------------------------------------------------
    # STUDY PLAN ENDPOINTS
    # ---------------------------------------------------------

    def test_create_study_plan(self):
        now = datetime.now().replace(microsecond=0)

        response = self.client.post(
            "/study-plans/",
            json={
                "student_id": self.student_id,
                "start_date": now.isoformat(),
                "end_date": (
                    now + timedelta(days=5)
                ).isoformat(),
                "status": "active",
            },
        )

        assert response.status_code == 201

        body = response.json()
        assert body["student_id"] == self.student_id
        assert body["status"] == "active"
        assert body["plan_id"] is not None

    def test_invalid_study_plan_dates_are_rejected(self):
        now = datetime.now().replace(microsecond=0)

        response = self.client.post(
            "/study-plans/",
            json={
                "student_id": self.student_id,
                "start_date": now.isoformat(),
                "end_date": (
                    now - timedelta(days=1)
                ).isoformat(),
                "status": "active",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "End date must be after start date."
        )

    def test_get_active_study_plan(self):
        response = self.client.get(
            f"/study-plans/student/{self.student_id}/active"
        )

        assert response.status_code == 200
        assert response.json()["plan_id"] == self.plan_id
        assert response.json()["status"] == "active"

    # ---------------------------------------------------------
    # STUDY PLAN ITEM ENDPOINTS
    # ---------------------------------------------------------

    def test_get_items_for_study_plan(self):
        response = self.client.get(
            f"/study-plan-items/plan/{self.plan_id}"
        )

        assert response.status_code == 200

        items = response.json()
        assert len(items) == 1
        assert items[0]["item_id"] == self.item_id
        assert items[0]["status"] == "pending"

    def test_update_session_status_to_completed(self):
        response = self.client.put(
            f"/study-plan-items/{self.item_id}/status",
            json={"status": "completed"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        # Verify the committed value through another DB session.
        verification_db = TestSessionLocal()

        try:
            item = (
                verification_db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.item_id == self.item_id
                )
                .one()
            )

            assert item.status == "completed"

        finally:
            verification_db.close()

    def test_update_session_status_to_in_progress(self):
        response = self.client.put(
            f"/study-plan-items/{self.item_id}/status",
            json={"status": "in_progress"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

    def test_update_session_status_on_inactive_plan_is_rejected(
        self,
    ):
        # Mark the existing plan as inactive.
        self.plan.status = "superseded"
        self.db.commit()

        response = self.client.put(
            f"/study-plan-items/{self.item_id}/status",
            json={"status": "completed"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == (
            "Cannot update an item in an inactive study plan"
        )

        # Confirm the rejected request did not change the item.
        verification_db = TestSessionLocal()

        try:
            item = (
                verification_db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.item_id == self.item_id
                )
                .one()
            )

            assert item.status == "pending"

        finally:
            verification_db.close()

    def test_invalid_session_status_is_rejected(self):
        response = self.client.put(
            f"/study-plan-items/{self.item_id}/status",
            json={"status": "overdue"},
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_missing_session_item_returns_404(self):
        response = self.client.put(
            "/study-plan-items/999999999/status",
            json={"status": "completed"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "Study plan item not found"
        )