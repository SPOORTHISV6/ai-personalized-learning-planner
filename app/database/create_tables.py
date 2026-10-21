from app.database.connection import engine, Base

from app.database.models import (
    Student,
    Subject,
    Topic,
    Performance,
    StudyPlan,
    StudyPlanItem,
    Quiz,
    QuizResult,
    Resource
)


Base.metadata.create_all(bind=engine)

print("All tables created successfully!")