from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional


class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    daily_available_hours: float
    learning_preference: Optional[str] = None


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: int
    name: str
    email: str
    daily_available_hours: float
    learning_preference: Optional[str]
