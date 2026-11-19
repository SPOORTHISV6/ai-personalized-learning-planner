from getpass import getpass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.config import get_database_url
from app.core.security import create_access_token
from app.database import connection
from app.database.models import Student
from app.main import app


# --------------------------------------------------
# 1. CONNECT TO RESTORED DATABASE USING READ-ONLY USER
# --------------------------------------------------

RESTORED_DATABASE = "ai_learning_planner_restore_test"
RESTORE_USERNAME = "restore_api_reader"

restore_password = getpass(
    f"Enter MySQL password for {RESTORE_USERNAME}: "
)

restored_url = make_url(get_database_url()).set(
    username=RESTORE_USERNAME,
    password=restore_password,
    database=RESTORED_DATABASE,
)

restored_engine = create_engine(
    restored_url,
    echo=False,
    pool_pre_ping=True,
)

RestoredSessionLocal = sessionmaker(
    bind=restored_engine,
    autoflush=False,
    autocommit=False,
)


def override_restored_db():
    """Route API database operations to restored database."""
    db = RestoredSessionLocal()
    try:
        yield db
    finally:
        db.close()


original_overrides = app.dependency_overrides.copy()


try:

    # --------------------------------------------------
    # 2. VERIFY DATABASE AND MYSQL ACCOUNT
    # --------------------------------------------------

    with restored_engine.connect() as conn:
        database_name = conn.execute(
            text("SELECT DATABASE()")
        ).scalar_one()

        current_user = conn.execute(
            text("SELECT CURRENT_USER()")
        ).scalar_one()

        print("Connected database:", database_name)
        print("Authenticated MySQL account:", current_user)

        if database_name != RESTORED_DATABASE:
            raise RuntimeError(
                "Connected to an unexpected database!"
            )

        if not current_user.startswith(RESTORE_USERNAME + "@"):
            raise RuntimeError(
                "Connected using an unexpected MySQL account!"
            )

    # --------------------------------------------------
    # 3. FIND AN EXISTING RESTORED STUDENT
    # --------------------------------------------------

    with RestoredSessionLocal() as db:
        student = (
            db.query(Student)
            .order_by(Student.student_id.asc())
            .first()
        )

        if student is None:
            raise RuntimeError(
                "No student records found in restored database."
            )

        student_id = student.student_id
        expected_name = student.name

        print("Restored student ID:", student_id)

    # --------------------------------------------------
    # 4. GENERATE JWT
    # --------------------------------------------------

    token = create_access_token(student_id)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print("JWT generated successfully.")

    # --------------------------------------------------
    # 5. OVERRIDE DATABASE DEPENDENCY
    # --------------------------------------------------

    app.dependency_overrides[
        connection.get_db
    ] = override_restored_db

    # --------------------------------------------------
    # 6. TEST AUTHENTICATED STUDENT PROFILE
    # --------------------------------------------------

    with TestClient(app) as client:

        profile_response = client.get(
            "/students/me",
            headers=headers,
        )

        print(
            "\nGET /students/me:",
            profile_response.status_code,
        )

        if profile_response.status_code != 200:
            raise RuntimeError(
                f"Profile API failed: {profile_response.text}"
            )

        profile = profile_response.json()

        assert profile["student_id"] == student_id
        assert profile["name"] == expected_name

        print("Student profile retrieved successfully.")

        # ----------------------------------------------
        # 7. TEST RESTORED DASHBOARD
        # ----------------------------------------------

        dashboard_response = client.get(
            f"/dashboard/student/{student_id}",
            headers=headers,
        )

        print(
            "\nGET /dashboard/student:",
            dashboard_response.status_code,
        )

        if dashboard_response.status_code != 200:
            raise RuntimeError(
                f"Dashboard API failed: "
                f"{dashboard_response.text}"
            )

        dashboard = dashboard_response.json()

        assert dashboard["student_id"] == student_id
        assert dashboard["student_name"] == expected_name

        print("Dashboard retrieved successfully.")

        print("\nDashboard statistics:")

        for key in [
            "total_subjects",
            "total_topics",
            "average_score",
            "weak_topics",
            "moderate_topics",
            "strong_topics",
            "active_study_plans",
            "active_total_sessions",
        ]:
            print(f"{key}: {dashboard[key]}")

    print(
        "\nSUCCESS: RESTORED DATABASE API VERIFICATION PASSED"
    )

finally:

    # --------------------------------------------------
    # 8. RESTORE ORIGINAL APP CONFIGURATION
    # --------------------------------------------------

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)

    restored_engine.dispose()

    print("\nDatabase engine disposed.")
    print("Original API dependency overrides restored.")
