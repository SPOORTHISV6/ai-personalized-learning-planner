
import pytest
from pydantic import ValidationError

from app.schemas.subject_schema import SubjectCreate
from app.schemas.topic_schema import TopicCreate


# ============================================================
# SUBJECT SCHEMA TESTS
# ============================================================

def test_valid_subject_data():
    subject = SubjectCreate(
        student_id=1,
        subject_name="  Database Management Systems  ",
        importance=5,
    )

    assert subject.student_id == 1
    assert subject.subject_name == "Database Management Systems"
    assert subject.importance == 5


def test_subject_optional_fields_can_be_none():
    subject = SubjectCreate(
        student_id=1,
        subject_name="DBMS",
    )

    assert subject.exam_date is None
    assert subject.importance is None


@pytest.mark.parametrize(
    "student_id",
    [0, -1, True, False, 1.5, "1"],
)
def test_subject_rejects_invalid_student_id(student_id):
    with pytest.raises(ValidationError):
        SubjectCreate(
            student_id=student_id,
            subject_name="DBMS",
        )


@pytest.mark.parametrize(
    "subject_name",
    ["", "   ", "A" * 101, 123, "DBMS\nInvalid"],
)
def test_subject_rejects_invalid_name(subject_name):
    with pytest.raises(ValidationError):
        SubjectCreate(
            student_id=1,
            subject_name=subject_name,
        )


@pytest.mark.parametrize(
    "importance",
    [0, 6, -1, True, False, 2.5, "3"],
)
def test_subject_rejects_invalid_importance(importance):
    with pytest.raises(ValidationError):
        SubjectCreate(
            student_id=1,
            subject_name="DBMS",
            importance=importance,
        )


@pytest.mark.parametrize("importance", [1, 2, 3, 4, 5])
def test_subject_accepts_valid_importance(importance):
    subject = SubjectCreate(
        student_id=1,
        subject_name="DBMS",
        importance=importance,
    )

    assert subject.importance == importance


# ============================================================
# TOPIC SCHEMA TESTS
# ============================================================

def test_valid_topic_data():
    topic = TopicCreate(
        subject_id=1,
        topic_name="  Database Normalization  ",
        difficulty=4,
        prerequisite_topic_id=2,
    )

    assert topic.subject_id == 1
    assert topic.topic_name == "Database Normalization"
    assert topic.difficulty == 4
    assert topic.prerequisite_topic_id == 2


def test_topic_optional_fields_can_be_none():
    topic = TopicCreate(
        subject_id=1,
        topic_name="SQL Basics",
    )

    assert topic.difficulty is None
    assert topic.prerequisite_topic_id is None


@pytest.mark.parametrize(
    "subject_id",
    [0, -1, True, False, 1.5, "1"],
)
def test_topic_rejects_invalid_subject_id(subject_id):
    with pytest.raises(ValidationError):
        TopicCreate(
            subject_id=subject_id,
            topic_name="SQL Basics",
        )


@pytest.mark.parametrize(
    "topic_name",
    ["", "   ", "A" * 151, 123, "SQL\nInvalid"],
)
def test_topic_rejects_invalid_name(topic_name):
    with pytest.raises(ValidationError):
        TopicCreate(
            subject_id=1,
            topic_name=topic_name,
        )


@pytest.mark.parametrize(
    "difficulty",
    [0, 6, -1, True, False, 2.5, "3"],
)
def test_topic_rejects_invalid_difficulty(difficulty):
    with pytest.raises(ValidationError):
        TopicCreate(
            subject_id=1,
            topic_name="SQL Basics",
            difficulty=difficulty,
        )


@pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
def test_topic_accepts_valid_difficulty(difficulty):
    topic = TopicCreate(
        subject_id=1,
        topic_name="SQL Basics",
        difficulty=difficulty,
    )

    assert topic.difficulty == difficulty


@pytest.mark.parametrize(
    "prerequisite_topic_id",
    [0, -1, True, False, 1.5, "2"],
)
def test_topic_rejects_invalid_prerequisite_id(
    prerequisite_topic_id,
):
    with pytest.raises(ValidationError):
        TopicCreate(
            subject_id=1,
            topic_name="SQL Joins",
            prerequisite_topic_id=prerequisite_topic_id,
        )


def test_topic_accepts_positive_prerequisite_id():
    topic = TopicCreate(
        subject_id=1,
        topic_name="SQL Joins",
        prerequisite_topic_id=2,
    )

    assert topic.prerequisite_topic_id == 2
