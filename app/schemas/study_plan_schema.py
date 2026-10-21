from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class StudyPlanCreate(BaseModel):
    student_id: int
    start_date: datetime
    end_date: datetime
    status: str = "active"


class StudyPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: int
    student_id: int
    start_date: datetime
    end_date: datetime
    status: str
    created_at: Optional[datetime] = None
