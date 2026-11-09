
import pytest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import (
    Student,
    Subject,
    Topic,
    Performance,
    StudyPlan,
    StudyPlanItem,
    Quiz,
    QuizResult,
)

from app.memory import student_memory


@pytest.fixture
def db_session(monkeypatch):
    """Create an isolated in-memory SQLite database."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(
        student_memory,
        "SessionLocal",
        TestingSessionLocal,
    )

    db = TestingSessionLocal()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def sample_student(db_session):
    """Create sample student and learning data."""

    student = Student(
        student_id=1,
        name="Test Student",
        email="test@example.com",
        daily_available_hours=4.0,
        learning_preference="Practice",
    )

    subject = Subject(
        subject_id=1,
        student_id=1,
        subject_name="DBMS",
    )

    topic1 = Topic(
        topic_id=1,
        subject_id=1,
        topic_name="Normalization",
        difficulty=4,
    )

    topic2 = Topic(
        topic_id=2,
        subject_id=1,
        topic_name="SQL Joins",
        difficulty=3,
    )

    topic3 = Topic(
        topic_id=3,
        subject_id=1,
        topic_name="SQL Basics",
        difficulty=2,
    )

    db_session.add_all([
        student,
        subject,
        topic1,
        topic2,
        topic3,
    ])

    db_session.flush()

    now = datetime(2026, 11, 1, 10, 0)

    # Normalization: latest 60, previous 40
    # SQL Joins: 80
    # SQL Basics: 45

    performances = [
        Performance(
            student_id=1,
            topic_id=1,
            score=40,
            attempt_date=now - timedelta(days=2),
        ),
        Performance(
            student_id=1,
            topic_id=1,
            score=60,
            attempt_date=now,
        ),
        Performance(
            student_id=1,
            topic_id=2,
            score=80,
            attempt_date=now - timedelta(days=1),
        ),
        Performance(
            student_id=1,
            topic_id=3,
            score=45,
            attempt_date=now - timedelta(days=1),
        ),
    ]

    db_session.add_all(performances)

    plan = StudyPlan(
        plan_id=1,
        student_id=1,
        start_date=now,
        end_date=now + timedelta(days=7),
        status="active",
        created_at=now,
    )

    completed_plan = StudyPlan(
        plan_id=2,
        student_id=1,
        start_date=now - timedelta(days=10),
        end_date=now - timedelta(days=3),
        status="completed",
        created_at=now - timedelta(days=10),
    )

    db_session.add_all([plan, completed_plan])
    db_session.flush()

    session_item = StudyPlanItem(
        item_id=1,
        plan_id=1,
        topic_id=1,
        scheduled_date=now + timedelta(days=1),
        duration_minutes=60,
        priority=1,
        status="pending",
    )

    db_session.add(session_item)

    quiz = Quiz(
        quiz_id=1,
        topic_id=1,
        title="Normalization Quiz",
        difficulty=3,
    )

    db_session.add(quiz)
    db_session.flush()

    quiz_result = QuizResult(
        result_id=1,
        quiz_id=1,
        student_id=1,
        score=75,
        attempted_at=now,
    )

    db_session.add(quiz_result)
    db_session.commit()

    return student


# =====================================================
# 1. PERFORMANCE TREND TESTS
# =====================================================

def test_empty_performance_trends():
    result = student_memory.calculate_performance_trends([])

    assert result == []


def test_single_performance_record():
    history = [
        {
            "topic_id": 1,
            "topic_name": "Python",
            "score": 80,
        }
    ]

    result = student_memory.calculate_performance_trends(history)

    assert len(result) == 1
    assert result[0]["trend"] == "insufficient_data"
    assert result[0]["latest_score"] == 80
    assert result[0]["previous_score"] is None
    assert result[0]["attempts"] == 1


def test_improving_performance_trend():
    history = [
        {"topic_id": 1, "topic_name": "DBMS", "score": 80},
        {"topic_id": 1, "topic_name": "DBMS", "score": 50},
    ]

    result = student_memory.calculate_performance_trends(history)

    assert result[0]["trend"] == "improving"
    assert result[0]["best_score"] == 80
    assert result[0]["average_score"] == 65


def test_declining_performance_trend():
    history = [
        {"topic_id": 1, "topic_name": "DBMS", "score": 40},
        {"topic_id": 1, "topic_name": "DBMS", "score": 80},
    ]

    result = student_memory.calculate_performance_trends(history)

    assert result[0]["trend"] == "declining"


def test_stable_performance_trend():
    history = [
        {"topic_id": 1, "topic_name": "DBMS", "score": 70},
        {"topic_id": 1, "topic_name": "DBMS", "score": 70},
    ]

    result = student_memory.calculate_performance_trends(history)

    assert result[0]["trend"] == "stable"


def test_multiple_topic_trends():
    history = [
        {"topic_id": 1, "topic_name": "DBMS", "score": 80},
        {"topic_id": 2, "topic_name": "Python", "score": 60},
        {"topic_id": 1, "topic_name": "DBMS", "score": 50},
    ]

    result = student_memory.calculate_performance_trends(history)

    assert len(result) == 2
    assert result[0]["attempts"] == 2
    assert result[1]["attempts"] == 1


# =====================================================
# 2. STUDENT MEMORY TESTS
# =====================================================

def test_student_not_found(db_session):
    result = student_memory.get_student_memory(999)

    assert result == {
        "error": "Student 999 not found"
    }


def test_student_profile(sample_student):
    result = student_memory.get_student_memory(1)

    assert result["profile"]["student_id"] == 1
    assert result["profile"]["name"] == "Test Student"
    assert result["profile"]["email"] == "test@example.com"
    assert result["profile"]["daily_available_hours"] == 4.0
    assert result["profile"]["learning_preference"] == "Practice"


def test_performance_history(sample_student):
    result = student_memory.get_student_memory(1)

    assert len(result["performance_history"]) == 4

    assert result["performance_history"][0]["topic_name"] == "Normalization"
    assert result["performance_history"][0]["score"] == 60.0


def test_latest_performance(sample_student):
    result = student_memory.get_student_memory(1)

    latest = {
        item["topic_name"]: item["score"]
        for item in result["latest_performance"]
    }

    assert latest["Normalization"] == 60.0
    assert latest["SQL Joins"] == 80.0
    assert latest["SQL Basics"] == 45.0


def test_topic_classification(sample_student):
    result = student_memory.get_student_memory(1)

    assert len(result["weak_topics"]) == 1
    assert len(result["moderate_topics"]) == 1
    assert len(result["strong_topics"]) == 1

    assert result["weak_topics"][0]["topic_name"] == "SQL Basics"
    assert result["moderate_topics"][0]["topic_name"] == "Normalization"
    assert result["strong_topics"][0]["topic_name"] == "SQL Joins"


def test_performance_trends_in_memory(sample_student):
    result = student_memory.get_student_memory(1)

    trends = {
        item["topic_name"]: item["trend"]
        for item in result["performance_trends"]
    }

    assert trends["Normalization"] == "improving"
    assert trends["SQL Joins"] == "insufficient_data"


def test_study_plan_history(sample_student):
    result = student_memory.get_student_memory(1)

    assert len(result["study_plan_history"]) == 2

    statuses = {
        plan["status"]
        for plan in result["study_plan_history"]
    }

    assert "active" in statuses
    assert "completed" in statuses


def test_session_history(sample_student):
    result = student_memory.get_student_memory(1)

    assert len(result["session_history"]) == 1

    session = result["session_history"][0]

    assert session["topic_name"] == "Normalization"
    assert session["duration_minutes"] == 60
    assert session["status"] == "pending"


def test_quiz_history(sample_student):
    result = student_memory.get_student_memory(1)

    assert len(result["quiz_history"]) == 1

    quiz = result["quiz_history"][0]

    assert quiz["quiz_title"] == "Normalization Quiz"
    assert quiz["score"] == 75.0
    assert quiz["topic_name"] == "Normalization"


def test_complete_memory_structure(sample_student):
    result = student_memory.get_student_memory(1)

    expected_keys = {
        "profile",
        "performance_history",
        "latest_performance",
        "performance_trends",
        "weak_topics",
        "moderate_topics",
        "strong_topics",
        "study_plan_history",
        "session_history",
        "quiz_history",
    }

    assert set(result.keys()) == expected_keys


def test_empty_memory_for_new_student(db_session):
    student = Student(
        student_id=2,
        name="New Student",
        email="new@example.com",
        daily_available_hours=3.0,
        learning_preference="Reading",
    )

    db_session.add(student)
    db_session.commit()

    result = student_memory.get_student_memory(2)

    assert result["profile"]["name"] == "New Student"
    assert result["performance_history"] == []
    assert result["latest_performance"] == []
    assert result["performance_trends"] == []
    assert result["weak_topics"] == []
    assert result["moderate_topics"] == []
    assert result["strong_topics"] == []
    assert result["study_plan_history"] == []
    assert result["session_history"] == []
    assert result["quiz_history"] == []
