from pydantic import BaseModel
from typing import Optional


class LearningGapResponse(BaseModel):
    topic_id: int
    topic_name: str
    score: float
    difficulty: int
    status: str
    priority: str
    prerequisite_topic_id: Optional[int] = None