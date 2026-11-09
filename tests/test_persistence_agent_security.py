
import pytest
from unittest.mock import Mock

import app.agents.persistence_agent as persistence_module


def valid_state():
    """Return a valid Persistence Agent workflow state."""
    return {
        "student_id": 1,
        "study_plan": {
            "student_id": 1,
            "sessions": [
                {
                    "topic_id": 3,
                    "date": "2026-11-06",
                    "duration_minutes": 60,
                    "priority": "high",
                }
            ],
        },
        "validation": {
            "valid": True,
        },
    }


def assert_rejected_before_database(monkeypatch, state):
    """
    Invalid input must be rejected before opening a database session.
    """
    session_factory = Mock(
        side_effect=AssertionError(
            "Database session should not be created for invalid input."
        )
    )

    monkeypatch.setattr(
        persistence_module,
        "SessionLocal",
        session_factory,
    )

    result = persistence_module.persistence_agent(state)

    assert isinstance(result, dict)
    assert result.get("next_action") == "stop"
    assert result.get("errors")

    session_factory.assert_not_called()


# ---------------------------------------------------------
# 1. WORKFLOW STATE VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "state",
    [
        None,
        [],
        (),
        "invalid state",
        123,
    ],
)
def test_rejects_malformed_workflow_state(monkeypatch, state):
    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 2. STUDENT ID VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "student_id",
    [
        None,
        True,
        False,
        0,
        -1,
        1.5,
        "invalid",
        "1",
    ],
)
def test_rejects_invalid_student_id(monkeypatch, student_id):
    state = valid_state()
    state["student_id"] = student_id

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 3. STUDY PLAN VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "study_plan",
    [
        None,
        [],
        "invalid plan",
        123,
    ],
)
def test_rejects_malformed_study_plan(monkeypatch, study_plan):
    state = valid_state()
    state["study_plan"] = study_plan

    assert_rejected_before_database(monkeypatch, state)


def test_rejects_missing_sessions(monkeypatch):
    state = valid_state()
    state["study_plan"]["sessions"] = []

    assert_rejected_before_database(monkeypatch, state)


@pytest.mark.parametrize(
    "sessions",
    [
        None,
        "invalid sessions",
        123,
        [None],
        ["invalid session"],
        [123],
    ],
)
def test_rejects_malformed_sessions(monkeypatch, sessions):
    state = valid_state()
    state["study_plan"]["sessions"] = sessions

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 4. VALIDATION RESULT CHECKS
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "validation",
    [
        None,
        [],
        "invalid validation",
        123,
        {"valid": False},
        {"valid": "true"},
        {"valid": 1},
    ],
)
def test_rejects_invalid_validation_result(monkeypatch, validation):
    state = valid_state()
    state["validation"] = validation

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 5. STUDENT OWNERSHIP CHECK
# ---------------------------------------------------------

def test_rejects_mismatched_plan_student_id(monkeypatch):
    state = valid_state()
    state["study_plan"]["student_id"] = 2

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 6. TOPIC ID VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "topic_id",
    [
        None,
        True,
        False,
        0,
        -1,
        3.5,
        "invalid",
    ],
)
def test_rejects_invalid_topic_id(monkeypatch, topic_id):
    state = valid_state()
    state["study_plan"]["sessions"][0]["topic_id"] = topic_id

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 7. SESSION DATE VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "session_date",
    [
        None,
        "",
        "invalid-date",
        "2026-02-30",
        "2026-13-01",
        "06-11-2026",
        "2026/11/06",
    ],
)
def test_rejects_invalid_session_date(monkeypatch, session_date):
    state = valid_state()
    state["study_plan"]["sessions"][0]["date"] = session_date

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 8. SESSION DURATION VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "duration",
    [
        None,
        True,
        False,
        0,
        -10,
        45.5,
        "invalid",
    ],
)
def test_rejects_invalid_session_duration(monkeypatch, duration):
    state = valid_state()
    state["study_plan"]["sessions"][0]["duration_minutes"] = duration

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 9. PRIORITY VALIDATION
# ---------------------------------------------------------

def test_rejects_unknown_priority(monkeypatch):
    state = valid_state()
    state["study_plan"]["sessions"][0]["priority"] = "urgent"

    assert_rejected_before_database(monkeypatch, state)


# ---------------------------------------------------------
# 10. MULTIPLE SESSION VALIDATION
# ---------------------------------------------------------

def test_rejects_invalid_topic_in_later_session(monkeypatch):
    state = valid_state()

    state["study_plan"]["sessions"].append({
        "topic_id": True,
        "date": "2026-11-07",
        "duration_minutes": 45,
        "priority": "medium",
    })

    assert_rejected_before_database(monkeypatch, state)


def test_rejects_invalid_date_in_later_session(monkeypatch):
    state = valid_state()

    state["study_plan"]["sessions"].append({
        "topic_id": 4,
        "date": "2026-02-30",
        "duration_minutes": 45,
        "priority": "medium",
    })

    assert_rejected_before_database(monkeypatch, state)


def test_rejects_invalid_duration_in_later_session(monkeypatch):
    state = valid_state()

    state["study_plan"]["sessions"].append({
        "topic_id": 4,
        "date": "2026-11-07",
        "duration_minutes": 45.5,
        "priority": "medium",
    })

    assert_rejected_before_database(monkeypatch, state)
