from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class StudyPlanItemCreate(BaseModel):
    plan_id: int
    topic_id: int
    scheduled_date: datetime
    duration_minutes: int
    priority: Optional[int] = None
    status: str = "pending"


class StudyPlanItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    plan_id: int
    topic_id: int
    scheduled_date: datetime
    duration_minutes: int
    priority: Optional[int]
    status: str


class StudyPlanItemStatusUpdate(BaseModel):
    status: str
