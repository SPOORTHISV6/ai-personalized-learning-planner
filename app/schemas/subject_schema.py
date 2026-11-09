
import unicodedata
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubjectCreate(BaseModel):
    student_id: int = Field(strict=True, gt=0)
    subject_name: str = Field(
        strict=True,
        min_length=1,
        max_length=100,
    )
    exam_date: Optional[datetime] = None
    importance: Optional[int] = Field(
        default=None,
        strict=True,
        ge=1,
        le=5,
    )

    @field_validator("subject_name", mode="before")
    @classmethod
    def validate_subject_name(cls, value):
        if not isinstance(value, str):
            raise ValueError("Subject name must be a string.")

        value = value.strip()

        if not value:
            raise ValueError("Subject name cannot be empty.")

        if any(
            unicodedata.category(character).startswith("C")
            for character in value
        ):
            raise ValueError(
                "Subject name cannot contain control characters."
            )

        return value


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_id: int
    student_id: int
    subject_name: str
    exam_date: Optional[datetime] = None
    importance: Optional[int] = None
