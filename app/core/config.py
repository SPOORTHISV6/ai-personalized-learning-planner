
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# Load local configuration without overwriting variables already supplied
# by the operating system or deployment environment.
load_dotenv(dotenv_path=ENV_FILE, override=False)


def _read_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value or not value.strip():
        raise RuntimeError(
            f"Required environment variable {name} is not configured."
        )

    return value.strip()


def _validate_mysql_url(
    env_name: str,
    expected_database: str,
) -> str:
    database_url = _read_required_env(env_name)

    try:
        parsed_url = make_url(database_url)
    except Exception:
        raise RuntimeError(
            f"{env_name} contains an invalid database URL."
        ) from None

    if parsed_url.drivername != "mysql+pymysql":
        raise RuntimeError(
            f"{env_name} must use the mysql+pymysql driver."
        )

    if parsed_url.database != expected_database:
        raise RuntimeError(
            f"{env_name} must target the "
            f"{expected_database} database."
        )

    if not parsed_url.username or not parsed_url.password:
        raise RuntimeError(
            f"{env_name} must contain database credentials."
        )

    return database_url


def get_database_url() -> str:
    """Return the application database URL.

    The application must never connect to the integration-test database.
    """
    return _validate_mysql_url(
        "DATABASE_URL",
        "ai_learning_planner",
    )


def get_test_database_url() -> str:
    """Return the dedicated integration-test database URL."""
    return _validate_mysql_url(
        "TEST_DATABASE_URL",
        "ai_learning_planner_test",
    )


def get_jwt_secret_key() -> str:
    """Return a sufficiently strong JWT signing secret."""
    secret_key = _read_required_env("JWT_SECRET_KEY")

    if len(secret_key) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be at least 32 characters long."
        )

    return secret_key


def get_api_base_url() -> str:
    """Return the frontend API URL."""
    api_base_url = os.getenv(
        "API_BASE_URL",
        "http://127.0.0.1:8001",
    ).strip().rstrip("/")

    if not api_base_url.startswith(("http://", "https://")):
        raise RuntimeError(
            "API_BASE_URL must start with http:// or https://."
        )

    return api_base_url
