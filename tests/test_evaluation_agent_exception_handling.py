
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agents.evaluation_agent import (
    SAFE_EVALUATION_ERROR,
    evaluation_agent,
)


def valid_state():
    return {
        "student_id": 5,
        "quiz_result_id": 101,
    }


def make_successful_database():
    db = MagicMock()

    quiz_result = SimpleNamespace(
        result_id=101,
        student_id=5,
        quiz_id=20,
        score=85.0,
        attempted_at=None,
    )

    quiz = SimpleNamespace(
        quiz_id=20,
        topic_id=30,
    )

    topic = SimpleNamespace(
        topic_id=30,
        subject_id=40,
        topic_name="Python Basics",
    )

    subject = SimpleNamespace(
        subject_id=40,
        student_id=5,
    )

    query_results = [
        quiz_result,
        quiz,
        topic,
        subject,
        None,
    ]

    query_objects = []

    for result in query_results:
        query = MagicMock()
        query.filter.return_value.first.return_value = result
        query_objects.append(query)

    db.query.side_effect = query_objects

    def refresh_performance(performance):
        performance.performance_id = 501

    db.refresh.side_effect = refresh_performance

    return db


class TestEvaluationAgentExceptionHandling:

    @patch("app.agents.evaluation_agent.SessionLocal")
    def test_database_session_creation_failure(
        self,
        mock_session,
    ):
        mock_session.side_effect = RuntimeError(
            "Sensitive database connection failure"
        )

        result = evaluation_agent(valid_state())

        assert result["next_action"] == "stop"
        assert result["errors"] == [SAFE_EVALUATION_ERROR]

    @patch("app.agents.evaluation_agent.SessionLocal")
    def test_rollback_failure_does_not_escape(
        self,
        mock_session,
    ):
        db = make_successful_database()
        mock_session.return_value = db

        db.rollback.side_effect = RuntimeError(
            "Rollback failed"
        )

        with patch(
            "app.agents.evaluation_agent.evaluate_score",
            side_effect=RuntimeError(
                "Scoring operation failed"
            ),
        ):
            result = evaluation_agent(valid_state())

        assert result["next_action"] == "stop"
        assert result["errors"] == [SAFE_EVALUATION_ERROR]
        db.rollback.assert_called_once()

    @patch("app.agents.evaluation_agent.SessionLocal")
    def test_database_close_failure_does_not_escape(
        self,
        mock_session,
    ):
        db = make_successful_database()
        mock_session.return_value = db

        db.close.side_effect = RuntimeError(
            "Database close failed"
        )

        result = evaluation_agent(valid_state())

        assert result["next_action"] == "reflection"
        assert result["evaluation"]["performance_recorded"] is True
        assert result["evaluation"]["performance_id"] == 501
        db.close.assert_called_once()

    @patch("app.agents.evaluation_agent.SessionLocal")
    def test_unexpected_scoring_failure_returns_safe_error(
        self,
        mock_session,
    ):
        db = make_successful_database()
        mock_session.return_value = db

        with patch(
            "app.agents.evaluation_agent.evaluate_score",
            side_effect=ValueError(
                "Internal scoring error"
            ),
        ):
            result = evaluation_agent(valid_state())

        assert result["next_action"] == "stop"
        assert result["errors"] == [SAFE_EVALUATION_ERROR]
