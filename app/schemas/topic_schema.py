
import unicodedata
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TopicCreate(BaseModel):
    subject_id: int = Field(strict=True, gt=0)
    topic_name: str = Field(
        strict=True,
        min_length=1,
        max_length=150,
    )
    difficulty: Optional[int] = Field(
        default=None,
        strict=True,
        ge=1,
        le=5,
    )
    prerequisite_topic_id: Optional[int] = Field(
        default=None,
        strict=True,
        gt=0,
    )

    @field_validator("topic_name", mode="before")
    @classmethod
    def validate_topic_name(cls, value):
        if not isinstance(value, str):
            raise ValueError("Topic name must be a string.")

        value = value.strip()

        if not value:
            raise ValueError("Topic name cannot be empty.")

        if any(
            unicodedata.category(character).startswith("C")
            for character in value
        ):
            raise ValueError(
                "Topic name cannot contain control characters."
            )

        return value


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic_id: int
    subject_id: int
    topic_name: str
    difficulty: Optional[int]
    prerequisite_topic_id: Optional[int]
