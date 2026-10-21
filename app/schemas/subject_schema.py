from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class SubjectCreate(BaseModel):
    student_id: int
    subject_name: str
    exam_date: Optional[datetime] = None
    importance: Optional[int] = None


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_id: int
    student_id: int
    subject_name: str
    exam_date: Optional[datetime] = None
    importance: Optional[int] = None
