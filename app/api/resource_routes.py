
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Topic, Resource, Student
from app.api.dependencies import get_current_student
from app.schemas.resource_schema import (
    ResourceCreate,
    ResourceResponse,
)

router = APIRouter(
    prefix="/resources",
    tags=["Resources"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_resource_admin(
    current_student: Student = Depends(get_current_student),
) -> Student:
    # The current Student model has no verified administrator role.
    # Keep resource creation disabled until admin authorization exists.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Resource creation requires administrator permissions.",
    )


@router.post(
    "/",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    resource: ResourceCreate,
    db: Session = Depends(get_db),
    admin: Student = Depends(require_resource_admin),
):
    topic = (
        db.query(Topic)
        .filter(Topic.topic_id == resource.topic_id)
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=404,
            detail="Topic not found",
        )

    new_resource = Resource(
        topic_id=resource.topic_id,
        title=resource.title,
        resource_type=resource.resource_type,
        source=resource.source,
        content_path=resource.content_path,
    )

    db.add(new_resource)
    db.commit()
    db.refresh(new_resource)

    return new_resource


@router.get(
    "/topic/{topic_id}",
    response_model=list[ResourceResponse],
)
def get_topic_resources(
    topic_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    topic = (
        db.query(Topic)
        .filter(Topic.topic_id == topic_id)
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=404,
            detail="Topic not found",
        )

    return (
        db.query(Resource)
        .filter(Resource.topic_id == topic_id)
        .order_by(Resource.resource_id.asc())
        .all()
    )


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    resource = (
        db.query(Resource)
        .filter(Resource.resource_id == resource_id)
        .first()
    )

    if resource is None:
        raise HTTPException(
            status_code=404,
            detail="Resource not found",
        )

    return resource
