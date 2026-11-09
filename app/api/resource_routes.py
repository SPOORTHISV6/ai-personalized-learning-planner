
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Topic, Resource, Student, Subject
from app.api.dependencies import get_current_student
from app.schemas.resource_schema import (
    ResourceCreate,
    ResourceResponse,
)


router = APIRouter(
    prefix="/resources",
    tags=["Resources"],
)


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# ADMIN AUTHORIZATION
# ============================================================

def require_resource_admin(
    current_student: Student = Depends(get_current_student),
) -> Student:
    """
    Allow resource creation only for authenticated administrators.

    The administrator role is verified using the Student record
    retrieved from the database.
    """

    if current_student.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resource creation requires administrator permissions.",
        )

    return current_student


# ============================================================
# CREATE RESOURCE
# ADMIN ONLY
# ============================================================

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
    """
    Create a learning resource for an existing topic.

    Only administrators can create resources.
    """

    topic = (
        db.query(Topic)
        .filter(Topic.topic_id == resource.topic_id)
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )

    new_resource = Resource(
        topic_id=resource.topic_id,
        title=resource.title,
        resource_type=resource.resource_type,
        source=resource.source,
        content_path=resource.content_path,
    )

    try:
        db.add(new_resource)
        db.commit()
        db.refresh(new_resource)

        return new_resource

    except Exception:
        db.rollback()
        raise


# ============================================================
# GET RESOURCES FOR A TOPIC
# AUTHENTICATED STUDENT: OWN TOPICS ONLY
# ============================================================

@router.get(
    "/topic/{topic_id}",
    response_model=list[ResourceResponse],
)
def get_topic_resources(
    topic_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """
    Return resources only when the requested topic belongs
    to the authenticated student.
    """

    topic = (
        db.query(Topic)
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(
            Topic.topic_id == topic_id,
            Subject.student_id == current_student.student_id,
        )
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )

    return (
        db.query(Resource)
        .filter(Resource.topic_id == topic.topic_id)
        .order_by(Resource.resource_id.asc())
        .all()
    )


# ============================================================
# GET RESOURCE BY ID
# AUTHENTICATED STUDENT: OWN RESOURCES ONLY
# ============================================================

@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """
    Return a resource only if its topic belongs to the
    authenticated student's subject.
    """

    resource = (
        db.query(Resource)
        .join(
            Topic,
            Resource.topic_id == Topic.topic_id,
        )
        .join(
            Subject,
            Topic.subject_id == Subject.subject_id,
        )
        .filter(
            Resource.resource_id == resource_id,
            Subject.student_id == current_student.student_id,
        )
        .first()
    )

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    return resource
