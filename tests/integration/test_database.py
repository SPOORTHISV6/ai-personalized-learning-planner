
import os
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database import models  # Registers all ORM models

from app.core.config import get_test_database_url


# Integration tests must be explicitly enabled.
if os.getenv("ALLOW_MYSQL_INTEGRATION_TESTS") != "1":
    raise RuntimeError(
        "Integration tests are disabled. Set "
        "$env:ALLOW_MYSQL_INTEGRATION_TESTS='1' "
        "before running them."
    )


# This URL is independent of the application database URL.
TEST_DATABASE_URL = get_test_database_url()


test_engine = create_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)


TestSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
)


def verify_test_database():
    """Fail early if this connection targets the wrong database."""
    with test_engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT DATABASE()")
        ).scalar_one()

    if database_name != "ai_learning_planner_test":
        raise RuntimeError(
            "Unsafe database target. Integration tests require "
            "ai_learning_planner_test."
        )


class MySQLIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        verify_test_database()
        Base.metadata.create_all(bind=test_engine)

    def setUp(self):
        self.db = TestSessionLocal()

    def tearDown(self):
        self.db.close()
