
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from app.database import backup_manager as bm


VALID_SQL_DUMP = (
    b"CREATE TABLE students (id INT);\n"
    b"INSERT INTO students VALUES (1);\n"
    b"-- Dump completed on 2026-11-14\n"
)


# --------------------------------------------------
# MYSQL OPTION FILE SECURITY
# --------------------------------------------------

def test_option_file_contains_credentials_without_exposing_them_in_command():
    url = make_url(
        "mysql+pymysql://backup_user:p%40ss%22word"
        "@localhost:3306/ai_learning_planner"
    )

    option_file = bm.create_mysql_option_file(url)

    try:
        content = option_file.read_text(encoding="utf-8")

        assert "[client]" in content
        assert 'user="backup_user"' in content
        assert 'password="p@ss\\"word"' in content
        assert 'host="localhost"' in content
        assert "port=3306" in content
        assert "protocol=TCP" in content

        assert "p@ss" not in str(option_file)

    finally:
        option_file.unlink(missing_ok=True)


def test_option_file_rejects_missing_credentials():
    url = make_url(
        "mysql+pymysql:///ai_learning_planner"
    )

    with pytest.raises(
        RuntimeError,
        match="credentials are missing"
    ):
        bm.create_mysql_option_file(url)


# --------------------------------------------------
# SQL BACKUP VALIDATION
# --------------------------------------------------

def test_verify_backup_accepts_valid_sql_dump(tmp_path):
    backup = tmp_path / "valid.sql"
    backup.write_bytes(VALID_SQL_DUMP)

    result = bm.verify_backup(backup)

    assert result["size"] == len(VALID_SQL_DUMP)
    assert result["tables"] == 1
    assert result["insert_statements"] == 1


def test_verify_backup_rejects_missing_file(tmp_path):
    backup = tmp_path / "missing.sql"

    with pytest.raises(
        RuntimeError,
        match="Backup file was not created"
    ):
        bm.verify_backup(backup)


def test_verify_backup_rejects_empty_file(tmp_path):
    backup = tmp_path / "empty.sql"
    backup.write_bytes(b"")

    with pytest.raises(
        RuntimeError,
        match="Backup file is empty"
    ):
        bm.verify_backup(backup)


def test_verify_backup_rejects_dump_without_create_table(tmp_path):
    backup = tmp_path / "invalid.sql"

    backup.write_bytes(
        b"INSERT INTO students VALUES (1);\n"
        b"-- Dump completed on 2026-11-14\n"
    )

    with pytest.raises(
        RuntimeError,
        match="No CREATE TABLE statements"
    ):
        bm.verify_backup(backup)


def test_verify_backup_rejects_incomplete_dump(tmp_path):
    backup = tmp_path / "incomplete.sql"

    backup.write_bytes(
        b"CREATE TABLE students (id INT);\n"
    )

    with pytest.raises(
        RuntimeError,
        match="completion marker is missing"
    ):
        bm.verify_backup(backup)


# --------------------------------------------------
# LOCAL ENCRYPTED BACKUP RETENTION
# --------------------------------------------------

def test_retention_keeps_latest_distinct_dates(tmp_path):
    filenames = [
        "ai_learning_planner_20261110_080000.sql.enc",
        "ai_learning_planner_20261110_120000.sql.enc",
        "ai_learning_planner_20261109_120000.sql.enc",
        "ai_learning_planner_20261108_120000.sql.enc",
    ]

    for filename in filenames:
        (tmp_path / filename).write_text(
            "encrypted backup",
            encoding="utf-8"
        )

    # Legacy plaintext backup must not be touched.
    legacy_backup = (
        tmp_path /
        "ai_learning_planner_20261108_120000.sql"
    )

    legacy_backup.write_text(
        "legacy plaintext backup",
        encoding="utf-8"
    )

    deleted = bm.apply_retention(
        backup_dir=tmp_path,
        keep_days=2
    )

    assert deleted == 1

    assert (
        tmp_path /
        "ai_learning_planner_20261110_080000.sql.enc"
    ).exists()

    assert (
        tmp_path /
        "ai_learning_planner_20261110_120000.sql.enc"
    ).exists()

    assert (
        tmp_path /
        "ai_learning_planner_20261109_120000.sql.enc"
    ).exists()

    assert not (
        tmp_path /
        "ai_learning_planner_20261108_120000.sql.enc"
    ).exists()

    assert legacy_backup.exists()


def test_retention_ignores_unexpected_filenames(tmp_path):
    unexpected = [
        "important_document.sql",
        "ai_learning_planner_invalid.sql.enc",
        "ai_learning_planner_20261110.sql.enc",
        "ai_learning_planner_20261110_120000.sql.partial",
        "ai_learning_planner_20261110_120000.sql.enc.partial",
    ]

    for filename in unexpected:
        (tmp_path / filename).write_text(
            "keep",
            encoding="utf-8"
        )

    deleted = bm.apply_retention(
        backup_dir=tmp_path,
        keep_days=1
    )

    assert deleted == 0

    for filename in unexpected:
        assert (tmp_path / filename).exists()


def test_retention_rejects_zero_days(tmp_path):
    with pytest.raises(
        ValueError,
        match="at least 1"
    ):
        bm.apply_retention(
            backup_dir=tmp_path,
            keep_days=0
        )


# --------------------------------------------------
# COMPLETE BACKUP EXECUTION
# --------------------------------------------------

def configure_backup_test_environment(
    monkeypatch,
    backup_dir
):
    monkeypatch.setattr(
        bm,
        "BACKUP_DIR",
        backup_dir
    )

    monkeypatch.setattr(
        bm,
        "get_backup_database_url",
        lambda: (
            "mysql+pymysql://learning_backup:"
            "test_password@localhost:3306/"
            "ai_learning_planner"
        )
    )

    monkeypatch.setattr(
        bm.shutil,
        "which",
        lambda name: "mysqldump.exe"
    )

    monkeypatch.setattr(
        bm,
        "apply_retention",
        lambda: 0
    )


def test_create_backup_publishes_only_verified_encrypted_backup(
    tmp_path,
    monkeypatch
):
    configure_backup_test_environment(
        monkeypatch,
        tmp_path
    )

    captured = {}

    def fake_subprocess_run(
        command,
        stdout,
        stderr,
        text,
        encoding,
        errors,
        timeout,
        check
    ):
        captured["command"] = command

        option_argument = next(
            argument
            for argument in command
            if argument.startswith(
                "--defaults-extra-file="
            )
        )

        option_file = Path(
            option_argument.split("=", 1)[1]
        )

        captured["option_file"] = option_file

        assert option_file.exists()

        stdout.write(VALID_SQL_DUMP)

        return SimpleNamespace(
            returncode=0,
            stderr=""
        )

    monkeypatch.setattr(
        bm.subprocess,
        "run",
        fake_subprocess_run
    )

    result = bm.create_backup()

    # Final artifact must be encrypted.
    assert result.exists()
    assert result.parent == tmp_path
    assert result.name.endswith(".sql.enc")
    assert result.suffix == ".enc"

    # Verify encrypted container header.
    from app.database.backup_encryption import MAGIC_HEADER

    with result.open("rb") as encrypted_file:
        assert encrypted_file.read(len(MAGIC_HEADER)) == MAGIC_HEADER

    # Authenticate and decrypt the final artifact.
    decrypted_path = tmp_path / "test_decrypted.sql"

    try:
        bm.decrypt_file(
            source=result,
            destination=decrypted_path,
        )

        assert decrypted_path.read_bytes() == VALID_SQL_DUMP

        verification = bm.verify_backup(decrypted_path)

        assert verification["tables"] == 1
        assert verification["insert_statements"] == 1

    finally:
        decrypted_path.unlink(missing_ok=True)

    # No temporary plaintext or encrypted files remain.
    assert list(tmp_path.glob("*.sql.partial")) == []
    assert list(tmp_path.glob("*.sql.enc.partial")) == []
    assert list(tmp_path.glob("*.verify.sql")) == []

    # MySQL option file must be removed.
    assert not captured["option_file"].exists()

    # Database password must not appear in command arguments.
    assert all(
        "test_password" not in argument
        for argument in captured["command"]
    )


def test_create_backup_removes_partial_files_after_dump_failure(
    tmp_path,
    monkeypatch
):
    configure_backup_test_environment(
        monkeypatch,
        tmp_path
    )

    captured = {}

    def fake_subprocess_run(
        command,
        stdout,
        stderr,
        text,
        encoding,
        errors,
        timeout,
        check
    ):
        option_argument = next(
            argument
            for argument in command
            if argument.startswith(
                "--defaults-extra-file="
            )
        )

        captured["option_file"] = Path(
            option_argument.split("=", 1)[1]
        )

        stdout.write(b"INCOMPLETE SQL")

        return SimpleNamespace(
            returncode=1,
            stderr="Simulated mysqldump failure"
        )

    monkeypatch.setattr(
        bm.subprocess,
        "run",
        fake_subprocess_run
    )

    with pytest.raises(
        RuntimeError,
        match="mysqldump failed"
    ):
        bm.create_backup()

    assert list(tmp_path.glob("*.sql.partial")) == []
    assert list(tmp_path.glob("*.sql.enc.partial")) == []
    assert list(tmp_path.glob("*.verify.sql")) == []
    assert list(tmp_path.glob("*.sql.enc")) == []

    assert not captured["option_file"].exists()


def test_create_backup_removes_files_when_verification_fails(
    tmp_path,
    monkeypatch
):
    configure_backup_test_environment(
        monkeypatch,
        tmp_path
    )

    captured = {}

    def fake_subprocess_run(
        command,
        stdout,
        stderr,
        text,
        encoding,
        errors,
        timeout,
        check
    ):
        option_argument = next(
            argument
            for argument in command
            if argument.startswith(
                "--defaults-extra-file="
            )
        )

        captured["option_file"] = Path(
            option_argument.split("=", 1)[1]
        )

        stdout.write(
            b"CREATE TABLE students (id INT);\n"
        )

        return SimpleNamespace(
            returncode=0,
            stderr=""
        )

    monkeypatch.setattr(
        bm.subprocess,
        "run",
        fake_subprocess_run
    )

    with pytest.raises(
        RuntimeError,
        match="completion marker is missing"
    ):
        bm.create_backup()

    assert list(tmp_path.glob("*.sql.partial")) == []
    assert list(tmp_path.glob("*.sql.enc.partial")) == []
    assert list(tmp_path.glob("*.verify.sql")) == []
    assert list(tmp_path.glob("*.sql.enc")) == []

    assert not captured["option_file"].exists()


def test_create_backup_rejects_unexpected_database(
    tmp_path,
    monkeypatch
):
    monkeypatch.setattr(
        bm,
        "BACKUP_DIR",
        tmp_path
    )

    monkeypatch.setattr(
        bm,
        "get_backup_database_url",
        lambda: (
            "mysql+pymysql://user:password"
            "@localhost:3306/another_database"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Refusing to back up unexpected database"
    ):
        bm.create_backup()

    assert list(tmp_path.iterdir()) == []
