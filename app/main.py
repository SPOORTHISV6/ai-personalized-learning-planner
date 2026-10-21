from fastapi import FastAPI

from app.api.student_routes import router as student_router
from app.api.subject_routes import router as subject_router
from app.api.topic_routes import router as topic_router
from app.api.performance_routes import router as performance_router
from app.api.learning_gap_routes import router as learning_gap_router
from app.api.study_plan_routes import router as study_plan_router
from app.api.study_plan_item_routes import router as study_plan_item_router

from app.api.quiz_routes import router as quiz_router
from app.api.quiz_result_routes import router as quiz_result_router
from app.api.resource_routes import router as resource_router
from app.api.dashboard_routes import router as dashboard_router
from app.api.auth_routes import router as auth_router

app = FastAPI(
    title="AI Personalized Learning Planner",
    description=(
        "Agentic AI based personalized learning "
        "and study planning system"
    ),
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "AI Personalized Learning Planner is running"
    }


# ------------------------------------------------------------
# API ROUTERS
# ------------------------------------------------------------

app.include_router(student_router)
app.include_router(subject_router)
app.include_router(topic_router)
app.include_router(performance_router)

app.include_router(learning_gap_router)

app.include_router(study_plan_router)
app.include_router(study_plan_item_router)

app.include_router(quiz_router)
app.include_router(quiz_result_router)

app.include_router(resource_router)

app.include_router(dashboard_router)
app.include_router(auth_router)