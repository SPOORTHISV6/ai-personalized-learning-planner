
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PerformanceCreate(BaseModel):
    student_id: int = Field(gt=0)
    topic_id: int = Field(gt=0)
    score: float = Field(ge=0, le=100, allow_inf_nan=False)


class PerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    performance_id: int
    student_id: int
    topic_id: int
    score: float
    attempt_date: Optional[datetime] = None
