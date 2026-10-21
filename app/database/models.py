
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.connection import Base


# ============================================================
# STUDENT
# ============================================================

class Student(Base):
    __tablename__ = "students"

    student_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    daily_available_hours = Column(Float, nullable=False)
    learning_preference = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    password_hash = Column(String(255), nullable=True)
    subjects = relationship(
        "Subject", back_populates="student",
        cascade="all, delete-orphan"
    )
    study_plans = relationship(
        "StudyPlan", back_populates="student",
        cascade="all, delete-orphan"
    )
    performances = relationship(
        "Performance", back_populates="student",
        cascade="all, delete-orphan"
    )
    quiz_results = relationship(
        "QuizResult", back_populates="student",
        cascade="all, delete-orphan"
    )


# ============================================================
# SUBJECT
# ============================================================

class Subject(Base):
    __tablename__ = "subjects"

    subject_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("students.student_id"), nullable=False
    )
    subject_name = Column(String(100), nullable=False)
    exam_date = Column(DateTime, nullable=True)
    importance = Column(Integer, nullable=True)

    student = relationship("Student", back_populates="subjects")
    topics = relationship(
        "Topic", back_populates="subject",
        cascade="all, delete-orphan"
    )


# ============================================================
# TOPIC
# ============================================================

class Topic(Base):
    __tablename__ = "topics"

    topic_id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(
        Integer, ForeignKey("subjects.subject_id"), nullable=False
    )
    topic_name = Column(String(150), nullable=False)
    difficulty = Column(Integer, nullable=True)
    prerequisite_topic_id = Column(
        Integer, ForeignKey("topics.topic_id"), nullable=True
    )

    subject = relationship("Subject", back_populates="topics")
    prerequisite = relationship(
        "Topic", remote_side=[topic_id],
        backref="dependent_topics"
    )


# ============================================================
# PERFORMANCE
# ============================================================

# ============================================================
# PERFORMANCE
# ============================================================

class Performance(Base):
    __tablename__ = "performance"

    performance_id = Column(Integer, primary_key=True, index=True)

    student_id = Column(
        Integer, ForeignKey("students.student_id"), nullable=False
    )

    topic_id = Column(
        Integer, ForeignKey("topics.topic_id"), nullable=False
    )

    # Links a quiz-generated performance record to its exact attempt.
    # NULL is allowed for manually recorded or historical performance.
    quiz_result_id = Column(
        Integer,
        ForeignKey("quiz_results.result_id", ondelete="SET NULL"),
        nullable=True,
    )

    score = Column(Float, nullable=False)
    attempt_date = Column(DateTime, server_default=func.now())

    student = relationship("Student", back_populates="performances")
    topic = relationship("Topic")

    __table_args__ = (
        UniqueConstraint(
            "quiz_result_id",
            name="uq_performance_quiz_result_id",
        ),
    )



# ============================================================
# STUDY PLAN
# ============================================================

class StudyPlan(Base):
    __tablename__ = "study_plans"

    plan_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("students.student_id"), nullable=False
    )
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime, server_default=func.now())

    student = relationship("Student", back_populates="study_plans")
    items = relationship(
        "StudyPlanItem", back_populates="plan",
        cascade="all, delete-orphan"
    )


# ============================================================
# STUDY PLAN ITEM
# ============================================================

class StudyPlanItem(Base):
    __tablename__ = "study_plan_items"

    item_id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer, ForeignKey("study_plans.plan_id"), nullable=False
    )
    topic_id = Column(
        Integer, ForeignKey("topics.topic_id"), nullable=False
    )
    scheduled_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    priority = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False, default="pending")

    plan = relationship("StudyPlan", back_populates="items")
    topic = relationship("Topic")


# ============================================================
# QUIZ
# ============================================================

class Quiz(Base):
    __tablename__ = "quizzes"

    quiz_id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(
        Integer, ForeignKey("topics.topic_id"), nullable=False
    )
    title = Column(String(150), nullable=False)
    difficulty = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    topic = relationship("Topic")
    questions = relationship(
        "QuizQuestion", back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.question_id"
    )
    results = relationship(
        "QuizResult", back_populates="quiz",
        cascade="all, delete-orphan"
    )


# ============================================================
# QUIZ QUESTION
# ============================================================

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    question_id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(
        Integer, ForeignKey("quizzes.quiz_id"), nullable=False, index=True
    )
    question_text = Column(Text, nullable=False)

    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500), nullable=False)
    option_d = Column(String(500), nullable=False)

    # Store A, B, C, or D. Never expose this field to quiz-taking clients.
    correct_option = Column(String(1), nullable=False)
    explanation = Column(Text, nullable=True)
    points = Column(Integer, nullable=False, default=1)

    quiz = relationship("Quiz", back_populates="questions")
    answers = relationship(
        "QuizAnswer", back_populates="question"
    )

    __table_args__ = (
        CheckConstraint(
            "correct_option IN ('A', 'B', 'C', 'D')",
            name="ck_quiz_question_correct_option"
        ),
        CheckConstraint(
            "points > 0",
            name="ck_quiz_question_positive_points"
        ),
    )


# ============================================================
# QUIZ RESULT
# ============================================================

class QuizResult(Base):
    __tablename__ = "quiz_results"

    result_id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(
        Integer, ForeignKey("quizzes.quiz_id"), nullable=False
    )
    student_id = Column(
        Integer, ForeignKey("students.student_id"), nullable=False
    )
    score = Column(Float, nullable=False)
    attempted_at = Column(DateTime, server_default=func.now())

    quiz = relationship("Quiz", back_populates="results")
    student = relationship("Student", back_populates="quiz_results")
    answers = relationship(
        "QuizAnswer", back_populates="result",
        cascade="all, delete-orphan"
    )


# ============================================================
# QUIZ ANSWER
# ============================================================

class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    answer_id = Column(Integer, primary_key=True, index=True)
    result_id = Column(
        Integer, ForeignKey("quiz_results.result_id"), nullable=False,
        index=True
    )
    question_id = Column(
        Integer, ForeignKey("quiz_questions.question_id"), nullable=False
    )
    selected_option = Column(String(1), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    points_awarded = Column(Integer, nullable=False, default=0)

    result = relationship("QuizResult", back_populates="answers")
    question = relationship("QuizQuestion", back_populates="answers")

    __table_args__ = (
        UniqueConstraint(
            "result_id", "question_id",
            name="uq_quiz_answer_result_question"
        ),
        CheckConstraint(
            "selected_option IN ('A', 'B', 'C', 'D')",
            name="ck_quiz_answer_selected_option"
        ),
    )


# ============================================================
# RESOURCE
# ============================================================

class Resource(Base):
    __tablename__ = "resources"

    resource_id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(
        Integer, ForeignKey("topics.topic_id"), nullable=False
    )
    title = Column(String(200), nullable=False)
    resource_type = Column(String(50), nullable=True)
    source = Column(String(500), nullable=True)
    content_path = Column(String(500), nullable=True)

    topic = relationship("Topic")
