from pydantic import BaseModel
from typing import List


class DashboardSummary(BaseModel):
    student_id: int
    student_name: str

    total_subjects: int
    total_topics: int

    average_score: float

    weak_topics: int
    moderate_topics: int
    strong_topics: int

    active_study_plans: int
    completed_sessions: int
    pending_sessions: int