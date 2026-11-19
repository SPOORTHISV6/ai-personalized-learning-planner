
import pytest

from app.core.config import (
    get_database_url,
    get_test_database_url,
)


PRODUCTION_URL = (
    "mysql+pymysql://learning_app:test-password"
    "@localhost/ai_learning_planner"
)

BROWSER_TEST_URL = (
    "mysql+pymysql://browser_test_app:test-password"
    "@localhost/ai_learning_planner_browser_test"
)

INTEGRATION_TEST_URL = (
    "mysql+pymysql://test_app:test-password"
    "@localhost/ai_learning_planner_test"
)


def test_production_database_is_default(monkeypatch):
    monkeypatch.delenv(
        "APP_USE_BROWSER_TEST_DB",
        raising=False,
    )
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_URL)

    assert get_database_url() == PRODUCTION_URL


def test_explicit_browser_mode_selects_browser_database(monkeypatch):
    monkeypatch.setenv("APP_USE_BROWSER_TEST_DB", "1")
    monkeypatch.setenv(
        "BROWSER_TEST_DATABASE_URL",
        BROWSER_TEST_URL,
    )
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_URL)

    assert get_database_url() == BROWSER_TEST_URL


def test_browser_mode_does_not_fall_back_to_production(monkeypatch):
    monkeypatch.setenv("APP_USE_BROWSER_TEST_DB", "1")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_URL)
    monkeypatch.delenv(
        "BROWSER_TEST_DATABASE_URL",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="BROWSER_TEST_DATABASE_URL",
    ):
        get_database_url()


def test_browser_mode_rejects_wrong_database(monkeypatch):
    monkeypatch.setenv("APP_USE_BROWSER_TEST_DB", "1")
    monkeypatch.setenv(
        "BROWSER_TEST_DATABASE_URL",
        INTEGRATION_TEST_URL,
    )

    with pytest.raises(
        RuntimeError,
        match="ai_learning_planner_browser_test",
    ):
        get_database_url()


def test_browser_mode_rejects_wrong_database_user(monkeypatch):
    wrong_user_url = (
        "mysql+pymysql://root:test-password"
        "@localhost/ai_learning_planner_browser_test"
    )

    monkeypatch.setenv("APP_USE_BROWSER_TEST_DB", "1")
    monkeypatch.setenv(
        "BROWSER_TEST_DATABASE_URL",
        wrong_user_url,
    )

    with pytest.raises(
        RuntimeError,
        match="browser_test_app",
    ):
        get_database_url()


def test_browser_mode_rejects_non_local_host(monkeypatch):
    remote_url = (
        "mysql+pymysql://browser_test_app:test-password"
        "@192.168.1.10/ai_learning_planner_browser_test"
    )

    monkeypatch.setenv("APP_USE_BROWSER_TEST_DB", "1")
    monkeypatch.setenv(
        "BROWSER_TEST_DATABASE_URL",
        remote_url,
    )

    with pytest.raises(
        RuntimeError,
        match="localhost",
    ):
        get_database_url()


def test_invalid_browser_mode_value_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_USE_BROWSER_TEST_DB", "true")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_URL)

    with pytest.raises(
        RuntimeError,
        match="must be either 0 or 1",
    ):
        get_database_url()


def test_integration_database_selector_remains_independent(monkeypatch):
    monkeypatch.setenv("APP_USE_BROWSER_TEST_DB", "1")
    monkeypatch.setenv(
        "BROWSER_TEST_DATABASE_URL",
        BROWSER_TEST_URL,
    )
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        INTEGRATION_TEST_URL,
    )

    assert get_test_database_url() == INTEGRATION_TEST_URL
