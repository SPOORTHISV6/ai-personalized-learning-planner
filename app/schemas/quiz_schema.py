
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator


# ============================================================
# QUIZ
# ============================================================

class QuizCreate(BaseModel):
    topic_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=150)
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)


class QuizResponse(BaseModel):
    quiz_id: int
    topic_id: int
    title: str
    difficulty: Optional[int] = None
    created_at: Optional[datetime] = None
    question_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# QUESTION CREATION
# ============================================================

class QuizQuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    option_a: str = Field(min_length=1, max_length=500)
    option_b: str = Field(min_length=1, max_length=500)
    option_c: str = Field(min_length=1, max_length=500)
    option_d: str = Field(min_length=1, max_length=500)
    correct_option: Literal["A", "B", "C", "D"]
    explanation: Optional[str] = None
    points: int = Field(default=1, gt=0)


class QuizQuestionResponse(BaseModel):
    question_id: int
    quiz_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    explanation: Optional[str] = None
    points: int = 1

    # Deliberately excludes correct_option.
    model_config = ConfigDict(from_attributes=True)


class QuizQuestionAdminResponse(QuizQuestionResponse):
    correct_option: Literal["A", "B", "C", "D"]


# ============================================================
# QUIZ SUBMISSION
# ============================================================

class QuizAnswerSubmission(BaseModel):
    question_id: int = Field(gt=0)
    selected_option: Literal["A", "B", "C", "D"]


class QuizSubmission(BaseModel):
    student_id: int = Field(gt=0)
    answers: List[QuizAnswerSubmission] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_questions(self):
        question_ids = [answer.question_id for answer in self.answers]

        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Each question can be answered only once.")

        return self


# ============================================================
# GRADED ANSWER
# ============================================================

class GradedAnswerResponse(BaseModel):
    question_id: int
    selected_option: str
    correct_option: str
    is_correct: bool
    points_awarded: int
    explanation: Optional[str] = None


class QuizSubmissionResponse(BaseModel):
    message: str
    workflow_status: str
    quiz_id: int
    student_id: int
    result_id: int
    score: float
    total_points: int
    earned_points: int
    answers: List[GradedAnswerResponse]
    evaluation: Optional[dict] = None
    validation: Optional[dict] = None
    study_plan: Optional[dict] = None
    user_feedback: Optional[str] = None
    errors: List[str] = []
