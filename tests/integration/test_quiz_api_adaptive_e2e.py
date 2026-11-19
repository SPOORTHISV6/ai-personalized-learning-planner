
"""End-to-end integration test for quiz submission and adaptive persistence.

Runs against the isolated MySQL integration-test database. The Resource Agent
is replaced with a deterministic empty-resource fixture so the test does not
need FAISS indexes or model downloads. All database-backed agents remain real.
"""

import importlib
import uuid

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_student
from app.database.connection import Base
from app.database.models import (
    Performance,
    Quiz,
    QuizAnswer,
    QuizQuestion,
    QuizResult,
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


def test_quiz_submission_runs_real_adaptive_workflow_and_persists_plan(
    monkeypatch,
):
    """A weak quiz attempt must create linked performance and study-plan rows."""

    # ---------------------------------------------------------------
    # 1. Verify the isolated test database and prepare test records.
    # ---------------------------------------------------------------

    verify_test_database()
    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()
    original_dependency_overrides = app.dependency_overrides.copy()

    student_id = None
    subject_id = None
    topic_id = None
    quiz_id = None

    try:
        unique_id = uuid.uuid4().hex[:12]

        student = Student(
            name="Adaptive API E2E Student",
            email=f"adaptive_api_e2e_{unique_id}@example.com",
            daily_available_hours=4.0,
            learning_preference="Practice",
        )
        db.add(student)
        db.flush()
        student_id = student.student_id

        subject = Subject(
            student_id=student_id,
            subject_name="DBMS",
        )
        db.add(subject)
        db.flush()
        subject_id = subject.subject_id

        topic = Topic(
            subject_id=subject_id,
            topic_name="Normalization",
            difficulty=4,
            prerequisite_topic_id=None,
        )
        db.add(topic)
        db.flush()
        topic_id = topic.topic_id

        quiz = Quiz(
            topic_id=topic_id,
            title="Normalization Adaptive E2E Quiz",
            difficulty=3,
        )
        db.add(quiz)
        db.flush()
        quiz_id = quiz.quiz_id

        question = QuizQuestion(
            quiz_id=quiz_id,
            question_text="Which normal form removes partial dependencies?",
            option_a="First Normal Form",
            option_b="Second Normal Form",
            option_c="Third Normal Form",
            option_d="BCNF",
            correct_option="B",
            explanation="Second Normal Form removes partial dependencies.",
            points=1,
        )
        db.add(question)
        db.commit()
        db.refresh(student)
        db.refresh(question)

        question_id = question.question_id

        # ---------------------------------------------------------------
        # 2. Patch every database-backed agent to use the test DB.
        # ---------------------------------------------------------------

        evaluation_module = importlib.import_module(
            "app.agents.evaluation_agent"
        )
        profile_module = importlib.import_module(
            "app.agents.profile_agent"
        )
        student_memory_module = importlib.import_module(
            "app.memory.student_memory"
        )
        learning_gap_agent_module = importlib.import_module(
            "app.agents.learning_gap_agent"
        )
        study_plan_module = importlib.import_module(
            "app.agents.study_plan_agent"
        )
        validation_module = importlib.import_module(
            "app.agents.validation_agent"
        )
        persistence_module = importlib.import_module(
            "app.agents.persistence_agent"
        )
        workflow_module = importlib.import_module(
            "app.workflows.adaptive_workflow"
        )
        quiz_routes_module = importlib.import_module(
            "app.api.quiz_result_routes"
        )

        for module in (
            evaluation_module,
            profile_module,
            student_memory_module,
                            learning_gap_agent_module,

            study_plan_module,
            validation_module,
            persistence_module,
        ):
            monkeypatch.setattr(module, "SessionLocal", TestSessionLocal)

        # Keep retrieval deterministic and offline. The real Study Plan Agent
        # handles the empty-resource case by generating a generic objective.
        def deterministic_resource_agent(state):
            return {
                "resources": [],
                "next_action": "study_plan",
            }

        monkeypatch.setattr(
            workflow_module,
            "resource_agent",
            deterministic_resource_agent,
        )

        # The workflow is compiled at import time. Build a fresh graph only
        # after the agent/session patches, then inject it into the API route.
        test_workflow = workflow_module.build_adaptive_workflow()
        monkeypatch.setattr(
            quiz_routes_module,
            "adaptive_workflow",
            test_workflow,
        )

        # ---------------------------------------------------------------
        # 3. Override the API's DB and authenticated-student dependencies.
        # ---------------------------------------------------------------

        def override_get_db():
            test_db = TestSessionLocal()
            try:
                yield test_db
            finally:
                test_db.close()

        app.dependency_overrides[
            quiz_routes_module.get_db
        ] = override_get_db
        app.dependency_overrides[
            get_current_student
        ] = lambda: student

        # ---------------------------------------------------------------
        # 4. Submit an intentionally incorrect answer through FastAPI.
        #    Correct answer is B; selecting A produces a 0% weak result.
        # ---------------------------------------------------------------

        client = TestClient(app)
        response = client.post(
            "/quiz-results/",
            params={"quiz_id": quiz_id},
            json={
                "student_id": student_id,
                "answers": [
                    {
                        "question_id": question_id,
                        "selected_option": "A",
                    }
                ],
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()

        # ---------------------------------------------------------------
        # 5. Verify the API response reflects a completed adaptive run.
        # ---------------------------------------------------------------

        assert payload["student_id"] == student_id
        assert payload["quiz_id"] == quiz_id
        assert payload["score"] == 0.0
        assert payload["workflow_status"] == "completed"
        assert payload["workflow_error"] is None
        assert payload["errors"] == []

        evaluation = payload["evaluation"]
        assert evaluation["student_id"] == student_id
        assert evaluation["quiz_result_id"] == payload["result_id"]
        assert evaluation["topic_id"] == topic_id
        assert evaluation["score"] == 0.0
        assert evaluation["level"] == "weak"
        assert evaluation["performance_recorded"] is True

        validation = payload["validation"]
        assert validation["valid"] is True
        assert payload["next_action"] == "complete"

        persisted_plan = payload["study_plan"]
        assert persisted_plan is not None
        assert persisted_plan["student_id"] == student_id
        assert persisted_plan["status"] == "active"
        assert persisted_plan["created_new_plan"] is True
        assert persisted_plan["total_sessions"] >= 1

        # ---------------------------------------------------------------
        # 6. Verify committed records through a fresh DB session.
        # ---------------------------------------------------------------

        verification_db = TestSessionLocal()
        try:
            result_id = payload["result_id"]
            plan_id = persisted_plan["plan_id"]

            saved_result = (
                verification_db.query(QuizResult)
                .filter(
                    QuizResult.result_id == result_id,
                    QuizResult.student_id == student_id,
                    QuizResult.quiz_id == quiz_id,
                )
                .first()
            )
            assert saved_result is not None
            assert saved_result.score == 0.0

            saved_answers = (
                verification_db.query(QuizAnswer)
                .filter(QuizAnswer.result_id == result_id)
                .all()
            )
            assert len(saved_answers) == 1
            assert saved_answers[0].question_id == question_id
            assert saved_answers[0].selected_option == "A"
            assert saved_answers[0].is_correct is False
            assert saved_answers[0].points_awarded == 0

            saved_performance = (
                verification_db.query(Performance)
                .filter(
                    Performance.quiz_result_id == result_id,
                    Performance.student_id == student_id,
                    Performance.topic_id == topic_id,
                )
                .one_or_none()
            )
            assert saved_performance is not None
            assert saved_performance.score == 0.0

            saved_plan = (
                verification_db.query(StudyPlan)
                .filter(
                    StudyPlan.plan_id == plan_id,
                    StudyPlan.student_id == student_id,
                )
                .one_or_none()
            )
            assert saved_plan is not None
            assert saved_plan.status == "active"

            saved_items = (
                verification_db.query(StudyPlanItem)
                .filter(StudyPlanItem.plan_id == plan_id)
                .all()
            )
            assert len(saved_items) >= 1
            assert any(item.topic_id == topic_id for item in saved_items)

            for item in saved_items:
                assert item.duration_minutes > 0
                assert item.priority == 5
                assert item.status == "pending"

        finally:
            verification_db.close()

    finally:
        # ---------------------------------------------------------------
        # 7. Remove only this test's rows, in FK-safe order.
        #
        # Use a NEW session. The setup session may hold a MySQL
        # REPEATABLE READ snapshot from before the API committed the
        # QuizResult and QuizAnswer rows. Reusing it can miss those rows.
        # ---------------------------------------------------------------

        db.close()
        cleanup_db = TestSessionLocal()

        try:
            if student_id is not None:
                plan_ids = [
                    row[0]
                    for row in (
                        cleanup_db.query(StudyPlan.plan_id)
                        .filter(StudyPlan.student_id == student_id)
                        .all()
                    )
                ]

                result_ids = [
                    row[0]
                    for row in (
                        cleanup_db.query(QuizResult.result_id)
                        .filter(QuizResult.student_id == student_id)
                        .all()
                    )
                ]

                question_ids = []
                if quiz_id is not None:
                    question_ids = [
                        row[0]
                        for row in (
                            cleanup_db.query(QuizQuestion.question_id)
                            .filter(QuizQuestion.quiz_id == quiz_id)
                            .all()
                        )
                    ]

                # Delete dependent answer rows first.
                if result_ids:
                    cleanup_db.query(QuizAnswer).filter(
                        QuizAnswer.result_id.in_(result_ids)
                    ).delete(synchronize_session=False)

                if question_ids:
                    cleanup_db.query(QuizAnswer).filter(
                        QuizAnswer.question_id.in_(question_ids)
                    ).delete(synchronize_session=False)

                cleanup_db.query(Performance).filter(
                    Performance.student_id == student_id
                ).delete(synchronize_session=False)

                if result_ids:
                    cleanup_db.query(QuizResult).filter(
                        QuizResult.result_id.in_(result_ids)
                    ).delete(synchronize_session=False)

                if plan_ids:
                    cleanup_db.query(StudyPlanItem).filter(
                        StudyPlanItem.plan_id.in_(plan_ids)
                    ).delete(synchronize_session=False)

                    cleanup_db.query(StudyPlan).filter(
                        StudyPlan.plan_id.in_(plan_ids)
                    ).delete(synchronize_session=False)

                if question_ids:
                    cleanup_db.query(QuizQuestion).filter(
                        QuizQuestion.question_id.in_(question_ids)
                    ).delete(synchronize_session=False)

                if quiz_id is not None:
                    cleanup_db.query(Quiz).filter(
                        Quiz.quiz_id == quiz_id
                    ).delete(synchronize_session=False)

                if topic_id is not None:
                    cleanup_db.query(Topic).filter(
                        Topic.topic_id == topic_id
                    ).delete(synchronize_session=False)

                if subject_id is not None:
                    cleanup_db.query(Subject).filter(
                        Subject.subject_id == subject_id
                    ).delete(synchronize_session=False)

                cleanup_db.query(Student).filter(
                    Student.student_id == student_id
                ).delete(synchronize_session=False)

                cleanup_db.commit()

        except Exception:
            cleanup_db.rollback()
            raise

        finally:
            cleanup_db.close()
            app.dependency_overrides.clear()
            app.dependency_overrides.update(original_dependency_overrides)
