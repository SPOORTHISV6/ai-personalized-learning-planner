from pydantic import BaseModel, ConfigDict
from typing import Optional


class ResourceCreate(BaseModel):
    topic_id: int
    title: str
    resource_type: Optional[str] = None
    source: Optional[str] = None
    content_path: Optional[str] = None


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resource_id: int
    topic_id: int
    title: str
    resource_type: Optional[str]
    source: Optional[str]
    content_path: Optional[str]
