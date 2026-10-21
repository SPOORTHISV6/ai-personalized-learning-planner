from pydantic import BaseModel, ConfigDict
from typing import Optional


class TopicCreate(BaseModel):
    subject_id: int
    topic_name: str
    difficulty: Optional[int] = None
    prerequisite_topic_id: Optional[int] = None


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic_id: int
    subject_id: int
    topic_name: str
    difficulty: Optional[int]
    prerequisite_topic_id: Optional[int]
