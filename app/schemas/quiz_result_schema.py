
from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


class QuizAnswerSubmission(BaseModel):
    """One answer submitted by a student."""

    question_id: PositiveInt
    selected_option: Literal["A", "B", "C", "D"]

    @field_validator("selected_option", mode="before")
    @classmethod
    def normalize_option(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return value


class QuizSubmission(BaseModel):
    """Complete submission for a quiz."""

    student_id: PositiveInt
    answers: List[QuizAnswerSubmission] = Field(min_length=1)

    @field_validator("answers")
    @classmethod
    def validate_unique_questions(cls, answers):
        question_ids = [answer.question_id for answer in answers]

        if len(question_ids) != len(set(question_ids)):
            raise ValueError(
                "A question can only be answered once."
            )

        return answers


class QuizResultResponse(BaseModel):
    """Stored quiz result."""

    result_id: int
    quiz_id: int
    student_id: int
    score: float
    attempted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
