
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api import auth_routes, dependencies
from app.core.security import (
    ALGORITHM,
    create_access_token,
    hash_password,
    verify_password,
)
from app.database.connection import Base
from app.database.models import Student
from app.main import app

from tests.integration.test_database import (
    TestSessionLocal,
    test_engine,
    verify_test_database,
)


TEST_SECRET = "test-secret-key-for-auth-integration-tests-123456"


def override_get_test_db():
    """Use only the isolated MySQL integration-test database."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_test_context(monkeypatch):
    """Prepare isolated authentication test data and dependencies."""

    verify_test_database()
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

    original_overrides = app.dependency_overrides.copy()

    app.dependency_overrides[auth_routes.get_db] = override_get_test_db
    app.dependency_overrides[dependencies.get_db] = override_get_test_db

    db = TestSessionLocal()
    unique_id = uuid4().hex

    student = Student(
        name="Authentication Test Student",
        email=f"auth_test_{unique_id}@example.com",
        password_hash=hash_password("CorrectPassword123!"),
        daily_available_hours=4.0,
        learning_preference="Practice",
        role="student",
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    student_id = student.student_id
    student_email = student.email
    created_student_ids = []

    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "student_id": student_id,
                "student_email": student_email,
                "password": "CorrectPassword123!",
                "secret": TEST_SECRET,
                "created_student_ids": created_student_ids,
            }

    finally:
        db.close()

        cleanup_db = TestSessionLocal()
        try:
            cleanup_ids = [student_id] + created_student_ids

            cleanup_db.query(Student).filter(
                Student.student_id.in_(cleanup_ids)
            ).delete(synchronize_session=False)

            cleanup_db.commit()

        finally:
            cleanup_db.close()

            app.dependency_overrides.clear()
            app.dependency_overrides.update(original_overrides)


# =========================================================
# PASSWORD SECURITY
# =========================================================

def test_password_is_stored_as_hash():
    password = "MySecurePassword123!"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("WrongPassword123!", password_hash)


def test_same_password_generates_different_hashes():
    password = "MySecurePassword123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash)
    assert verify_password(password, second_hash)


# =========================================================
# REGISTRATION SECURITY
# =========================================================

def test_register_student_successfully(auth_test_context):
    client = auth_test_context["client"]
    email = f"new_student_{uuid4().hex}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "name": "New Test Student",
            "email": email,
            "password": "NewPassword123!",
            "daily_available_hours": 3.5,
            "learning_preference": "Practice",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == email
    assert "password_hash" not in data

    auth_test_context["created_student_ids"].append(
        data["student_id"]
    )


def test_registration_assigns_student_role_by_default(auth_test_context):
    client = auth_test_context["client"]
    email = f"role_test_{uuid4().hex}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "name": "Role Escalation Test",
            "email": email,
            "password": "SecurePassword123!",
            "daily_available_hours": 4,
            "learning_preference": "Practice",
        },
    )

    assert response.status_code == 201

    registered_id = response.json()["student_id"]

    auth_test_context["created_student_ids"].append(
        registered_id
    )

    db = TestSessionLocal()
    try:
        registered_student = (
            db.query(Student)
            .filter(Student.student_id == registered_id)
            .first()
        )

        assert registered_student is not None
        assert registered_student.role == "student"

    finally:
        db.close()


def test_registration_rejects_admin_role(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/register",
        json={
            "name": "Admin Injection Test",
            "email": f"admin_injection_{uuid4().hex}@example.com",
            "password": "SecurePassword123!",
            "daily_available_hours": 4,
            "learning_preference": "Practice",
            "role": "admin",
        },
    )

    assert response.status_code == 422


def test_registration_rejects_duplicate_email(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/register",
        json={
            "name": "Duplicate Student",
            "email": auth_test_context["student_email"],
            "password": "AnotherPassword123!",
            "daily_available_hours": 4,
            "learning_preference": "Practice",
        },
    )

    assert response.status_code == 409


def test_registration_rejects_short_password(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/register",
        json={
            "name": "Short Password Student",
            "email": f"short_{uuid4().hex}@example.com",
            "password": "123",
            "daily_available_hours": 4,
            "learning_preference": "Practice",
        },
    )

    assert response.status_code == 422


# =========================================================
# LOGIN SECURITY
# =========================================================

def test_login_with_valid_credentials(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/login",
        json={
            "email": auth_test_context["student_email"],
            "password": auth_test_context["password"],
        },
    )

    assert response.status_code == 200

    token_data = response.json()

    assert token_data["access_token"]
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == 1800


def test_login_rejects_incorrect_password(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/login",
        json={
            "email": auth_test_context["student_email"],
            "password": "IncorrectPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_rejects_unknown_email(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/login",
        json={
            "email": f"unknown_{uuid4().hex}@example.com",
            "password": "SomePassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


# =========================================================
# JWT AUTHENTICATION
# =========================================================

def test_missing_bearer_token_is_rejected(auth_test_context):
    response = auth_test_context["client"].get("/auth/me")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_malformed_jwt_is_rejected(auth_test_context):
    response = auth_test_context["client"].get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


def test_expired_jwt_is_rejected(auth_test_context):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(auth_test_context["student_id"]),
        "iat": now - timedelta(minutes=60),
        "exp": now - timedelta(minutes=30),
    }

    expired_token = jwt.encode(
        payload,
        auth_test_context["secret"],
        algorithm=ALGORITHM,
    )

    response = auth_test_context["client"].get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_wrong_secret_jwt_is_rejected(auth_test_context):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(auth_test_context["student_id"]),
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }

    invalid_token = jwt.encode(
        payload,
        "different-secret-key-for-testing-123456789",
        algorithm=ALGORITHM,
    )

    response = auth_test_context["client"].get(
        "/auth/me",
        headers={"Authorization": f"Bearer {invalid_token}"},
    )

    assert response.status_code == 401


def test_token_with_nonexistent_student_is_rejected(auth_test_context):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": "999999999",
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }

    token = jwt.encode(
        payload,
        auth_test_context["secret"],
        algorithm=ALGORITHM,
    )

    response = auth_test_context["client"].get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# =========================================================
# PROTECTED ENDPOINTS
# =========================================================

def test_authenticated_student_can_access_me(auth_test_context):
    client = auth_test_context["client"]

    login_response = client.post(
        "/auth/login",
        json={
            "email": auth_test_context["student_email"],
            "password": auth_test_context["password"],
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["student_id"] == auth_test_context["student_id"]
    assert response.json()["email"] == auth_test_context["student_email"]
    assert "password_hash" not in response.json()


def test_invalid_token_cannot_access_protected_endpoint(auth_test_context):
    response = auth_test_context["client"].get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


# =========================================================
# ADDITIONAL AUTHENTICATION SECURITY REGRESSION TESTS
# =========================================================

def test_registration_rejects_whitespace_only_name(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/register",
        json={
            "name": "     ",
            "email": f"spaces_{uuid4().hex}@example.com",
            "password": "SecurePassword123!",
            "daily_available_hours": 4,
            "learning_preference": "Practice",
        },
    )

    assert response.status_code == 422


def test_registration_rejects_boolean_daily_hours(auth_test_context):
    response = auth_test_context["client"].post(
        "/auth/register",
        json={
            "name": "Boolean Hours Test",
            "email": f"boolean_{uuid4().hex}@example.com",
            "password": "SecurePassword123!",
            "daily_available_hours": True,
            "learning_preference": "Practice",
        },
    )

    assert response.status_code == 422


def test_registration_rejects_email_exceeding_database_length(
    auth_test_context,
):
    long_email = f"{'a' * 140}@example.com"

    response = auth_test_context["client"].post(
        "/auth/register",
        json={
            "name": "Long Email Test",
            "email": long_email,
            "password": "SecurePassword123!",
            "daily_available_hours": 4,
            "learning_preference": "Practice",
        },
    )

    assert response.status_code == 422


def test_login_handles_malformed_stored_password_hash(
    auth_test_context,
):
    db = TestSessionLocal()
    original_hash = None

    try:
        student = (
            db.query(Student)
            .filter(
                Student.student_id == auth_test_context["student_id"]
            )
            .first()
        )

        assert student is not None

        original_hash = student.password_hash
        student.password_hash = "malformed-password-hash"
        db.commit()

        response = auth_test_context["client"].post(
            "/auth/login",
            json={
                "email": auth_test_context["student_email"],
                "password": auth_test_context["password"],
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."

    finally:
        if original_hash is not None:
            student = (
                db.query(Student)
                .filter(
                    Student.student_id == auth_test_context["student_id"]
                )
                .first()
            )

            if student is not None:
                student.password_hash = original_hash
                db.commit()

        db.close()


# =========================================================
# TOKEN CREATION INPUT VALIDATION
# =========================================================

@pytest.mark.parametrize(
    "student_id",
    [0, -1, True, 1.5, "invalid"],
)
def test_access_token_rejects_invalid_student_id(
    student_id,
    monkeypatch,
):
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

    with pytest.raises(ValueError):
        create_access_token(student_id)


@pytest.mark.parametrize(
    "expires_minutes",
    [0, -1, True, 1.5, "invalid"],
)
def test_access_token_rejects_invalid_expiration(
    expires_minutes,
    monkeypatch,
):
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

    with pytest.raises(ValueError):
        create_access_token(
            student_id=1,
            expires_minutes=expires_minutes,
        )
