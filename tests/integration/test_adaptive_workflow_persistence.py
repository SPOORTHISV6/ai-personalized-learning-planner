
import unittest
import uuid
from contextlib import ExitStack
from unittest.mock import patch

from app.database.connection import Base
from app.database.models import (
    Student,
    Subject,
    Topic,
    StudyPlan,
    StudyPlanItem,
)

from app.workflows import adaptive_workflow as workflow_module

from tests.integration.test_database import (
    TestSessionLocal,
    test_engine,
    verify_test_database,
)


class TestAdaptiveWorkflowPersistenceIntegration(unittest.TestCase):

    # =========================================================
    # SETUP
    # =========================================================

    @classmethod
    def setUpClass(cls):
        verify_test_database()
        Base.metadata.create_all(bind=test_engine)

    def setUp(self):

        self.student_id = None
        self.subject_id = None
        self.topic_id = None

        self.db = TestSessionLocal()

        unique_id = uuid.uuid4().hex[:12]

        # -----------------------------------------------------
        # CREATE TEST STUDENT
        # -----------------------------------------------------

        self.student = Student(
            name="Adaptive Persistence Test Student",
            email=f"adaptive_test_{unique_id}@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
        )

        self.db.add(self.student)
        self.db.commit()
        self.db.refresh(self.student)

        self.student_id = self.student.student_id

        # -----------------------------------------------------
        # CREATE TEST SUBJECT
        # -----------------------------------------------------

        self.subject = Subject(
            student_id=self.student_id,
            subject_name="DBMS",
        )

        self.db.add(self.subject)
        self.db.commit()
        self.db.refresh(self.subject)

        self.subject_id = self.subject.subject_id

        # -----------------------------------------------------
        # CREATE TEST TOPIC
        # -----------------------------------------------------

        self.topic = Topic(
            subject_id=self.subject_id,
            topic_name="Normalization",
            difficulty=4,
            prerequisite_topic_id=None,
        )

        self.db.add(self.topic)
        self.db.commit()
        self.db.refresh(self.topic)

        self.topic_id = self.topic.topic_id

        # The workflow and verification use independent sessions.
        self.db.close()
        self.db = None

        print("\n[Integration Test] Test database records created.")
        print(f"[Integration Test] Student ID: {self.student_id}")
        print(f"[Integration Test] Subject ID: {self.subject_id}")
        print(f"[Integration Test] Topic ID: {self.topic_id}")

    # =========================================================
    # MOCK UPSTREAM AGENTS
    # =========================================================

    def fake_evaluation(self, state):

        return {
            "evaluation": {
                "quiz_result_id": state["quiz_result_id"],
                "student_id": state["student_id"],
                "topic_id": self.topic_id,
                "topic_name": "Normalization",
                "score": 40.0,
                "level": "weak",
                "recommended_action": "practice",
                "performance_recorded": True,
            },
            "next_action": "reflection",
        }

    def fake_memory(self, state):

        return {
            "student_memory": {
                "latest_performance": [
                    {
                        "topic_id": self.topic_id,
                        "topic_name": "Normalization",
                        "score": 40.0,
                    }
                ]
            }
        }

    def fake_profile(self, state):

        return {
            "student_profile": {
                "student_id": state["student_id"],
                "daily_available_hours": 4.0,
                "learning_preference": "Practice",
            }
        }

    def fake_learning_gaps(self, state):

        return {
            "learning_gaps": [
                {
                    "topic_id": self.topic_id,
                    "topic_name": "Normalization",
                    "subject_id": self.subject_id,
                    "subject_name": "DBMS",
                    "score": 40.0,
                    "difficulty": 4,
                    "status": "weak",
                    "priority": "high",
                    "prerequisite_topic_id": None,
                }
            ],
            "next_action": "resource",
        }

    def fake_resources(self, state):

        return {
            "resources": []
        }

    # =========================================================
    # BUILD WORKFLOW WITH SELECTIVE MOCKING
    # =========================================================

    def build_test_workflow(self, stack):

        # Mock only upstream agents.
        # Reflection, Study Plan, Validation and Persistence
        # remain real.

        stack.enter_context(
            patch.object(
                workflow_module,
                "evaluation_agent",
                self.fake_evaluation,
            )
        )

        stack.enter_context(
            patch.object(
                workflow_module,
                "memory_agent",
                self.fake_memory,
            )
        )

        stack.enter_context(
            patch.object(
                workflow_module,
                "profile_agent",
                self.fake_profile,
            )
        )

        stack.enter_context(
            patch.object(
                workflow_module,
                "learning_gap_agent",
                self.fake_learning_gaps,
            )
        )

        stack.enter_context(
            patch.object(
                workflow_module,
                "resource_agent",
                self.fake_resources,
            )
        )

        # Make all real downstream agents use the
        # isolated MySQL integration-test database.

        stack.enter_context(
            patch(
                "app.agents.study_plan_agent.SessionLocal",
                TestSessionLocal,
            )
        )

        stack.enter_context(
            patch(
                "app.agents.validation_agent.SessionLocal",
                TestSessionLocal,
            )
        )

        stack.enter_context(
            patch(
                "app.agents.persistence_agent.SessionLocal",
                TestSessionLocal,
            )
        )

        return workflow_module.build_adaptive_workflow()

    # =========================================================
    # MAIN INTEGRATION TEST
    # =========================================================

    def test_weak_performance_creates_real_database_study_plan(self):

        with ExitStack() as stack:

            workflow = self.build_test_workflow(stack)

            result = workflow.invoke({
                "student_id": self.student_id,
                "quiz_result_id": 987654,
            })

        # -----------------------------------------------------
        # 1. VERIFY EVALUATION
        # -----------------------------------------------------

        evaluation = result.get("evaluation", {})

        self.assertEqual(
            evaluation.get("level"),
            "weak",
        )

        self.assertEqual(
            evaluation.get("score"),
            40.0,
        )

        # -----------------------------------------------------
        # 2. VERIFY REFLECTION
        # -----------------------------------------------------

        self.assertEqual(
            result.get("next_action"),
            "complete",
        )

        # -----------------------------------------------------
        # 3. VERIFY STUDY PLAN GENERATION
        # -----------------------------------------------------

        study_plan = result.get("study_plan")

        self.assertIsNotNone(study_plan)

        sessions = study_plan.get("sessions", [])

        self.assertGreater(
            len(sessions),
            0,
        )

        normalization_sessions = [
            session
            for session in sessions
            if session.get("topic_id") == self.topic_id
        ]

        self.assertTrue(normalization_sessions)

        normalization = normalization_sessions[0]

        self.assertEqual(
            normalization["priority"],
            "high",
        )

        self.assertEqual(
            normalization["learning_status"],
            "weak",
        )

        self.assertGreater(
            normalization["duration_minutes"],
            0,
        )

        # -----------------------------------------------------
        # 4. VERIFY VALIDATION
        # -----------------------------------------------------

        validation = result.get("validation", {})

        self.assertIs(
            validation.get("valid"),
            True,
        )

        # -----------------------------------------------------
        # 5. VERIFY PERSISTENCE RESULT
        # -----------------------------------------------------

        self.assertEqual(
            result.get("persistence_action"),
            "created_new_plan",
        )

        persisted_plan = result.get("persisted_plan")

        self.assertIsNotNone(persisted_plan)

        self.assertEqual(
            persisted_plan["student_id"],
            self.student_id,
        )

        self.assertEqual(
            persisted_plan["status"],
            "active",
        )

        self.assertTrue(
            persisted_plan["created_new_plan"]
        )

        plan_id = persisted_plan["plan_id"]

        # -----------------------------------------------------
        # 6. VERIFY ACTUAL MYSQL RECORDS
        # -----------------------------------------------------

        verification_db = TestSessionLocal()

        try:

            saved_plan = (
                verification_db.query(StudyPlan)
                .filter(
                    StudyPlan.plan_id == plan_id,
                    StudyPlan.student_id == self.student_id,
                )
                .first()
            )

            self.assertIsNotNone(
                saved_plan,
                "StudyPlan was not committed to the test database.",
            )

            saved_items = (
                verification_db.query(StudyPlanItem)
                .filter(
                    StudyPlanItem.plan_id == plan_id
                )
                .all()
            )

            self.assertEqual(
                len(saved_items),
                len(sessions),
            )

            self.assertGreater(
                len(saved_items),
                0,
            )

            for item in saved_items:

                self.assertEqual(
                    item.topic_id,
                    self.topic_id,
                )

                self.assertGreater(
                    item.duration_minutes,
                    0,
                )

                # Persistence Agent converts high priority
                # into database priority 5.

                self.assertEqual(
                    item.priority,
                    5,
                )

                self.assertEqual(
                    item.status,
                    "pending",
                )

            print(
                "\n[Integration Test] Real adaptive study plan "
                "persisted successfully."
            )

            print(
                f"[Integration Test] Plan ID: {plan_id}"
            )

            print(
                f"[Integration Test] Sessions saved: {len(saved_items)}"
            )

            print(
                "[Integration Test] Database verification passed."
            )

        finally:
            verification_db.close()

    # =========================================================
    # SAFE DATABASE CLEANUP
    # =========================================================

    def tearDown(self):

        cleanup_db = TestSessionLocal()

        try:

            # -------------------------------------------------
            # 1. FIND STUDENT'S TEST PLANS
            # -------------------------------------------------

            plan_ids = []

            if self.student_id is not None:

                plan_ids = [
                    row[0]
                    for row in (
                        cleanup_db.query(StudyPlan.plan_id)
                        .filter(
                            StudyPlan.student_id == self.student_id
                        )
                        .all()
                    )
                ]

            # -------------------------------------------------
            # 2. DELETE ITEMS REFERENCING THE TEST TOPIC
            #
            # This is important:
            # A topic can still be referenced by an item even
            # if its plan was not found using student_id.
            # -------------------------------------------------

            if self.topic_id is not None:

                cleanup_db.query(StudyPlanItem).filter(
                    StudyPlanItem.topic_id == self.topic_id
                ).delete(
                    synchronize_session=False
                )

            # -------------------------------------------------
            # 3. DELETE ITEMS BELONGING TO TEST PLANS
            # -------------------------------------------------

            if plan_ids:

                cleanup_db.query(StudyPlanItem).filter(
                    StudyPlanItem.plan_id.in_(plan_ids)
                ).delete(
                    synchronize_session=False
                )

            cleanup_db.commit()

            # -------------------------------------------------
            # 4. DELETE TEST STUDY PLANS
            # -------------------------------------------------

            if plan_ids:

                cleanup_db.query(StudyPlan).filter(
                    StudyPlan.plan_id.in_(plan_ids),
                    StudyPlan.student_id == self.student_id,
                ).delete(
                    synchronize_session=False
                )

                cleanup_db.commit()

            # -------------------------------------------------
            # 5. DELETE TEST TOPIC
            # -------------------------------------------------

            if self.topic_id is not None:

                cleanup_db.query(Topic).filter(
                    Topic.topic_id == self.topic_id
                ).delete(
                    synchronize_session=False
                )

                cleanup_db.commit()

            # -------------------------------------------------
            # 6. DELETE TEST SUBJECT
            # -------------------------------------------------

            if self.subject_id is not None:

                cleanup_db.query(Subject).filter(
                    Subject.subject_id == self.subject_id
                ).delete(
                    synchronize_session=False
                )

                cleanup_db.commit()

            # -------------------------------------------------
            # 7. DELETE TEST STUDENT
            # -------------------------------------------------

            if self.student_id is not None:

                cleanup_db.query(Student).filter(
                    Student.student_id == self.student_id
                ).delete(
                    synchronize_session=False
                )

                cleanup_db.commit()

            print(
                "\n[Integration Test] Test database cleanup completed."
            )

        except Exception:

            cleanup_db.rollback()
            raise

        finally:

            cleanup_db.close()

            if self.db is not None:
                self.db.close()
                self.db = None


if __name__ == "__main__":
    unittest.main()
