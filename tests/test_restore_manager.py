
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from app.database import restore_manager as rm


VALID_SQL_DUMP = (
    b"CREATE TABLE students (id INT);\n"
    b"INSERT INTO students VALUES (1);\n"
    b"-- Dump completed on 2026-11-14\n"
)


# --------------------------------------------------
# RESTORE TARGET SECURITY
# --------------------------------------------------

def test_restore_target_accepts_dedicated_database(monkeypatch):
    monkeypatch.setattr(
        rm,
        "get_restore_database_url",
        lambda: (
            "mysql+pymysql://restore_user:password"
            "@localhost:3306/ai_learning_planner_restore_test"
        ),
    )

    result = rm.validate_restore_target()

    assert result.database == rm.EXPECTED_RESTORE_DATABASE
    assert result.drivername == "mysql+pymysql"


@pytest.mark.parametrize(
    "database",
    [
        "ai_learning_planner",
        "ai_learning_planner_test",
        "another_database",
    ],
)
def test_restore_target_rejects_unauthorized_database(
    monkeypatch,
    database,
):
    monkeypatch.setattr(
        rm,
        "get_restore_database_url",
        lambda: (
            f"mysql+pymysql://restore_user:password"
            f"@localhost:3306/{database}"
        ),
    )

    with pytest.raises(RuntimeError, match="Unsafe restore target"):
        rm.validate_restore_target()


def test_restore_target_rejects_wrong_driver(monkeypatch):
    monkeypatch.setattr(
        rm,
        "get_restore_database_url",
        lambda: (
            "postgresql://restore_user:password"
            "@localhost:5432/ai_learning_planner_restore_test"
        ),
    )

    with pytest.raises(
    RuntimeError,
    match=r"mysql\+pymysql",
):
        rm.validate_restore_target()


# --------------------------------------------------
# SQL DUMP VALIDATION
# --------------------------------------------------

def create_sql_dump(tmp_path, content):
    sql_path = tmp_path / "restore_test.sql"
    sql_path.write_bytes(content)
    return sql_path


def test_validate_restore_sql_accepts_valid_dump(tmp_path):
    sql_path = create_sql_dump(
        tmp_path,
        VALID_SQL_DUMP,
    )

    result = rm.validate_restore_sql(sql_path)

    assert result["tables"] == 1
    assert result["insert_statements"] == 1
    assert result["size"] == len(VALID_SQL_DUMP)


@pytest.mark.parametrize(
    "statement",
    [
        b"USE another_database;\n",
        b"CREATE DATABASE another_database;\n",
        b"DROP DATABASE another_database;\n",
    ],
)
def test_validate_restore_sql_rejects_database_commands(
    tmp_path,
    statement,
):
    sql_path = create_sql_dump(
        tmp_path,
        VALID_SQL_DUMP + statement,
    )

    with pytest.raises(
        RuntimeError,
        match="database-level command",
    ):
        rm.validate_restore_sql(sql_path)


@pytest.mark.parametrize(
    "statement",
    [
        b"/*!50000 USE another_database */;\n",
        b"/*!50000 CREATE DATABASE another_database */;\n",
        b"/*!50000 DROP DATABASE another_database */;\n",
    ],
)
def test_validate_restore_sql_rejects_executable_comment_commands(
    tmp_path,
    statement,
):
    sql_path = create_sql_dump(
        tmp_path,
        VALID_SQL_DUMP + statement,
    )

    with pytest.raises(
        RuntimeError,
        match="database-level command",
    ):
        rm.validate_restore_sql(sql_path)


def test_validate_restore_sql_allows_safe_mysql_executable_comments(
    tmp_path,
):
    content = (
        b"CREATE TABLE students (id INT);\n"
        b"/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n"
        b"INSERT INTO students VALUES (1);\n"
        b"-- Dump completed on 2026-11-14\n"
    )

    sql_path = create_sql_dump(
        tmp_path,
        content,
    )

    result = rm.validate_restore_sql(sql_path)

    assert result["tables"] == 1


def test_validate_restore_sql_does_not_reject_forbidden_words_in_strings(
    tmp_path,
):
    content = (
        b"CREATE TABLE students (message VARCHAR(255));\n"
        b"INSERT INTO students VALUES "
        b"('USE another_database or DROP DATABASE example');\n"
        b"-- Dump completed on 2026-11-14\n"
    )

    sql_path = create_sql_dump(
        tmp_path,
        content,
    )

    result = rm.validate_restore_sql(sql_path)

    assert result["tables"] == 1


# --------------------------------------------------
# RESTORE CONFIRMATION
# --------------------------------------------------

def test_restore_requires_explicit_confirmation(monkeypatch):
    called = {"target_validation": False}

    def fake_validate_target():
        called["target_validation"] = True
        raise AssertionError("Target validation should not run")

    monkeypatch.setattr(
        rm,
        "validate_restore_target",
        fake_validate_target,
    )

    with pytest.raises(ValueError, match="confirmation"):
        rm.restore_backup_from_drive(
            file_id="test-file-id",
            confirmation="WRONG_CONFIRMATION",
        )

    assert called["target_validation"] is False


# --------------------------------------------------
# RESTORE EXECUTION
# --------------------------------------------------

def configure_restore_environment(
    monkeypatch,
    tmp_path,
):
    database_url = make_url(
        "mysql+pymysql://restore_user:password"
        "@localhost:3306/ai_learning_planner_restore_test"
    )

    monkeypatch.setattr(
        rm,
        "validate_restore_target",
        lambda: database_url,
    )

    monkeypatch.setattr(
        rm,
        "check_restore_connection",
        lambda url: {
            "database": rm.EXPECTED_RESTORE_DATABASE,
            "mysql_user": "restore_user@localhost",
        },
    )

    monkeypatch.setattr(
        rm.shutil,
        "which",
        lambda name: "mysql.exe",
    )

    monkeypatch.setattr(
        rm,
        "get_encryption_key",
        lambda: b"x" * 32,
    )

    def fake_download_backup(file_id, destination):
        encrypted_path = (
            Path(destination)
            / "ai_learning_planner_20261115_120000.sql.enc"
        )

        encrypted_path.write_bytes(b"fake-encrypted-content")

        return {
            "file_name": encrypted_path.name,
            "destination": str(encrypted_path),
            "sha256": "test-checksum",
            "verified": True,
        }

    monkeypatch.setattr(
        rm,
        "download_backup",
        fake_download_backup,
    )

    def fake_decrypt_file(source, destination, key):
        destination = Path(destination)
        destination.write_bytes(VALID_SQL_DUMP)

        return {
            "decrypted_size": len(VALID_SQL_DUMP),
        }

    monkeypatch.setattr(
        rm,
        "decrypt_file",
        fake_decrypt_file,
    )

    option_file = tmp_path / "restore.cnf"

    def fake_create_option_file(database_url):
        option_file.write_text(
            "[client]\nuser=restore_user\n",
            encoding="utf-8",
        )
        return option_file

    monkeypatch.setattr(
        rm,
        "create_mysql_option_file",
        fake_create_option_file,
    )

    return option_file


def test_restore_successfully_uses_dynamic_backup_filename(
    tmp_path,
    monkeypatch,
):
    option_file = configure_restore_environment(
        monkeypatch,
        tmp_path,
    )

    captured = {}

    def fake_subprocess_run(
        command,
        stdin,
        stdout,
        stderr,
        timeout,
        check,
    ):
        captured["command"] = command
        captured["timeout"] = timeout

        assert stdin.read() == VALID_SQL_DUMP

        return SimpleNamespace(
            returncode=0,
            stdout=b"",
            stderr=b"",
        )

    monkeypatch.setattr(
        rm.subprocess,
        "run",
        fake_subprocess_run,
    )

    result = rm.restore_backup_from_drive(
        file_id="test-file-id",
        confirmation=rm.RESTORE_CONFIRMATION,
    )

    assert result["status"] == "SUCCESS"

    assert (
        result["backup_file"]
        == "ai_learning_planner_20261115_120000.sql.enc"
    )

    assert result["database"] == rm.EXPECTED_RESTORE_DATABASE
    assert result["encryption"] == "AES-256-GCM"
    assert result["authenticated"] is True
    assert result["tables_in_dump"] == 1

    assert "--database" in captured["command"]
    assert rm.EXPECTED_RESTORE_DATABASE in captured["command"]

    assert captured["timeout"] == rm.RESTORE_TIMEOUT_SECONDS

    # Temporary MySQL credentials must be removed.
    assert not option_file.exists()


def test_restore_rejects_unverified_cloud_backup(
    tmp_path,
    monkeypatch,
):
    configure_restore_environment(
        monkeypatch,
        tmp_path,
    )

    def fake_download_backup(file_id, destination):
        return {
            "file_name": "backup.sql.enc",
            "destination": str(Path(destination) / "backup.sql.enc"),
            "verified": False,
        }

    monkeypatch.setattr(
        rm,
        "download_backup",
        fake_download_backup,
    )

    with pytest.raises(
        RuntimeError,
        match="verification did not succeed",
    ):
        rm.restore_backup_from_drive(
            file_id="test-file-id",
            confirmation=rm.RESTORE_CONFIRMATION,
        )


def test_restore_rejects_downloaded_path_outside_temp_directory(
    tmp_path,
    monkeypatch,
):
    configure_restore_environment(
        monkeypatch,
        tmp_path,
    )

    def fake_download_backup(file_id, destination):
        outside_path = tmp_path / "outside.sql.enc"
        outside_path.write_bytes(b"fake-encrypted-content")

        return {
            "file_name": outside_path.name,
            "destination": str(outside_path),
            "verified": True,
        }

    monkeypatch.setattr(
        rm,
        "download_backup",
        fake_download_backup,
    )

    with pytest.raises(
        RuntimeError,
        match="Downloaded backup path",
    ):
        rm.restore_backup_from_drive(
            file_id="test-file-id",
            confirmation=rm.RESTORE_CONFIRMATION,
        )


def test_restore_rejects_mysql_import_failure(
    tmp_path,
    monkeypatch,
):
    option_file = configure_restore_environment(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.setattr(
        rm.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout=b"",
            stderr=b"Simulated MySQL import failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated MySQL import failure",
    ):
        rm.restore_backup_from_drive(
            file_id="test-file-id",
            confirmation=rm.RESTORE_CONFIRMATION,
        )

    assert not option_file.exists()


def test_restore_rejects_missing_mysql_client(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        rm,
        "validate_restore_target",
        lambda: make_url(
            "mysql+pymysql://restore_user:password"
            "@localhost:3306/ai_learning_planner_restore_test"
        ),
    )

    monkeypatch.setattr(
        rm,
        "check_restore_connection",
        lambda url: {
            "database": rm.EXPECTED_RESTORE_DATABASE,
            "mysql_user": "restore_user@localhost",
        },
    )

    monkeypatch.setattr(
        rm.shutil,
        "which",
        lambda name: None,
    )

    with pytest.raises(
        RuntimeError,
        match="MySQL client was not found",
    ):
        rm.restore_backup_from_drive(
            file_id="test-file-id",
            confirmation=rm.RESTORE_CONFIRMATION,
        )
