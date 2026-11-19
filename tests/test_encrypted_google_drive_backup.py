import hashlib
from unittest.mock import MagicMock

import pytest
from pathlib import Path
from app.database.backup_encryption import encrypt_file

from app.database import encrypted_google_drive_backup as encrypted_drive

from app.database.encrypted_google_drive_backup import (
    BACKUP_FILENAME_PATTERN,
    apply_encrypted_cloud_retention,
    validate_encrypted_backup,
    upload_backup,
    download_backup,
)


VALID_SQL_DUMP = (
    b"CREATE TABLE students (id INT);\n"
    b"INSERT INTO students VALUES (1);\n"
    b"-- Dump completed on 2026-11-14\n"
)

TEST_KEY = bytes.fromhex(
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
)

VALID_BACKUP_NAME = (
    "ai_learning_planner_20261114_120000.sql.enc"
)


# --------------------------------------------------
# TEST HELPERS
# --------------------------------------------------

def create_encrypted_test_backup(tmp_path, monkeypatch):
    """Create a valid encrypted SQL backup for testing."""

    monkeypatch.setenv(
        "BACKUP_ENCRYPTION_KEY",
        TEST_KEY.hex()
    )

    sql_path = tmp_path / "source.sql"

    encrypted_path = tmp_path / VALID_BACKUP_NAME

    sql_path.write_bytes(VALID_SQL_DUMP)

    encrypt_file(
        source=sql_path,
        destination=encrypted_path,
        key=TEST_KEY
    )

    return encrypted_path


def create_mock_drive_service():
    """Create a mocked Google Drive service."""

    service = MagicMock()

    return service


def mock_execute_with_retry(monkeypatch):
    """Execute mocked Google API requests without network access."""

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "execute_with_retry",
        lambda request, operation_name=None: request.execute()
    )


def mock_drive_authentication(
    monkeypatch,
    service,
):
    """Mock Google Drive authentication and folder lookup."""

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "authenticate_google_drive",
        lambda: service
    )

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "get_or_create_backup_folder",
        lambda service: "backup-folder-123"
    )


# --------------------------------------------------
# FILENAME VALIDATION
# --------------------------------------------------

def test_encrypted_backup_filename_pattern_accepts_valid_name():

    assert BACKUP_FILENAME_PATTERN.fullmatch(
        VALID_BACKUP_NAME
    )


def test_encrypted_backup_filename_pattern_rejects_plaintext():

    assert not BACKUP_FILENAME_PATTERN.fullmatch(
        "ai_learning_planner_20261114_120000.sql"
    )


# --------------------------------------------------
# ENCRYPTED BACKUP VALIDATION
# --------------------------------------------------

def test_encrypted_backup_validation_rejects_missing_file(tmp_path):

    with pytest.raises(
        FileNotFoundError,
        match="not found"
    ):

        validate_encrypted_backup(
            tmp_path / VALID_BACKUP_NAME
        )


def test_encrypted_backup_validation_accepts_valid_backup(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    result = validate_encrypted_backup(encrypted_path)

    assert result["authenticated"] is True

    assert result["encryption"] == "AES-256-GCM"

    assert result["tables"] == 1

    assert result["insert_statements"] == 1

    assert result["decrypted_size"] == len(VALID_SQL_DUMP)

    assert result["decrypted_size_verified"] is True

    # The original plaintext source remains available.
    assert (
        tmp_path / "source.sql"
    ).read_bytes() == VALID_SQL_DUMP


def test_encrypted_backup_validation_rejects_modified_ciphertext(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    encrypted_data = bytearray(
        encrypted_path.read_bytes()
    )

    # Modify ciphertext while leaving the header and nonce intact.
    ciphertext_position = 8 + 12

    encrypted_data[ciphertext_position] ^= 0x01

    encrypted_path.write_bytes(encrypted_data)

    with pytest.raises(
        RuntimeError,
        match="authentication failed"
    ):

        validate_encrypted_backup(encrypted_path)


def test_encrypted_backup_validation_rejects_missing_key(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    monkeypatch.delenv(
        "BACKUP_ENCRYPTION_KEY",
        raising=False
    )

    with pytest.raises(
        RuntimeError,
        match="not configured"
    ):

        validate_encrypted_backup(encrypted_path)


# --------------------------------------------------
# ENCRYPTED CLOUD RETENTION
# --------------------------------------------------

def test_encrypted_cloud_retention_keeps_latest_seven_dates():

    service = create_mock_drive_service()

    files = [
        {
            "id": f"file-{day}",
            "name": (
                f"ai_learning_planner_202611{day:02d}_120000.sql.enc"
            ),
            "size": "1024",
            "description": "SHA256:test",
        }
        for day in range(1, 11)
    ]

    service.files.return_value.list.return_value.execute.return_value = {
        "files": files
    }

    result = apply_encrypted_cloud_retention(
        service,
        "backup-folder-123",
        keep_dates=7,
    )

    assert result["total_backups"] == 10

    assert result["retained_dates"] == 7

    assert result["retained_files"] == 7

    assert result["trashed_files"] == 3

    assert service.files.return_value.update.call_count == 3


def test_encrypted_cloud_retention_keeps_multiple_files_per_date():

    service = create_mock_drive_service()

    files = [
        {
            "id": "file-1",
            "name": "ai_learning_planner_20261110_080000.sql.enc",
        },
        {
            "id": "file-2",
            "name": "ai_learning_planner_20261110_120000.sql.enc",
        },
        {
            "id": "file-3",
            "name": "ai_learning_planner_20261109_120000.sql.enc",
        },
    ]

    service.files.return_value.list.return_value.execute.return_value = {
        "files": files
    }

    result = apply_encrypted_cloud_retention(
        service,
        "backup-folder-123",
        keep_dates=2,
    )

    assert result["retained_files"] == 3

    assert result["trashed_files"] == 0

    service.files.return_value.update.assert_not_called()


def test_encrypted_cloud_retention_ignores_plaintext_backups():

    service = create_mock_drive_service()

    files = [
        {
            "id": "plain-1",
            "name": "ai_learning_planner_20261110_120000.sql",
        },
        {
            "id": "other-1",
            "name": "important_document.pdf",
        },
        {
            "id": "invalid-1",
            "name": "ai_learning_planner_invalid.sql.enc",
        },
    ]

    service.files.return_value.list.return_value.execute.return_value = {
        "files": files
    }

    result = apply_encrypted_cloud_retention(
        service,
        "backup-folder-123",
        keep_dates=7,
    )

    assert result["total_backups"] == 0

    assert result["trashed_files"] == 0

    service.files.return_value.update.assert_not_called()


def test_encrypted_cloud_retention_rejects_zero_days():

    service = create_mock_drive_service()

    with pytest.raises(
        ValueError,
        match="at least 1"
    ):

        apply_encrypted_cloud_retention(
            service,
            "backup-folder-123",
            keep_dates=0,
        )


# --------------------------------------------------
# ENCRYPTED GOOGLE DRIVE UPLOAD
# --------------------------------------------------

def test_encrypted_upload_success(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    service = create_mock_drive_service()

    mock_execute_with_retry(monkeypatch)

    mock_drive_authentication(
        monkeypatch,
        service
    )

    checksum = hashlib.sha256(
        encrypted_path.read_bytes()
    ).hexdigest()

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "find_existing_backup",
        lambda *args: None
    )

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "calculate_sha256",
        lambda path: checksum
    )

    monkeypatch.setattr(
        encrypted_drive,
        "apply_encrypted_cloud_retention",
        lambda *args, **kwargs: {
            "total_backups": 1,
            "retained_dates": 1,
            "retained_files": 1,
            "trashed_files": 0,
        }
    )

    service.files.return_value.create.return_value.execute.return_value = {
        "id": "drive-file-123",
        "name": VALID_BACKUP_NAME,
        "size": str(encrypted_path.stat().st_size),
        "description": f"SHA256:{checksum}",
        "parents": ["backup-folder-123"],
    }

    result = upload_backup(encrypted_path)

    assert result["file_id"] == "drive-file-123"

    assert result["file_name"] == VALID_BACKUP_NAME

    assert result["sha256"] == checksum

    assert result["already_exists"] is False

    assert result["local_verification"]["authenticated"] is True

    service.files.return_value.create.assert_called_once()


def test_encrypted_upload_detects_existing_duplicate(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    service = create_mock_drive_service()

    mock_execute_with_retry(monkeypatch)

    mock_drive_authentication(
        monkeypatch,
        service
    )

    checksum = hashlib.sha256(
        encrypted_path.read_bytes()
    ).hexdigest()

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "calculate_sha256",
        lambda path: checksum
    )

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "find_existing_backup",
        lambda *args: {
            "id": "existing-drive-file",
            "name": VALID_BACKUP_NAME,
            "size": str(encrypted_path.stat().st_size),
            "description": f"SHA256:{checksum}",
        }
    )

    monkeypatch.setattr(
        encrypted_drive,
        "apply_encrypted_cloud_retention",
        lambda *args, **kwargs: {
            "total_backups": 1,
            "retained_dates": 1,
            "retained_files": 1,
            "trashed_files": 0,
        }
    )

    result = upload_backup(encrypted_path)

    assert result["file_id"] == "existing-drive-file"

    assert result["already_exists"] is True

    # A duplicate must not trigger another upload.
    service.files.return_value.create.assert_not_called()


def test_encrypted_upload_cleans_up_unverified_cloud_file(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    service = create_mock_drive_service()

    mock_execute_with_retry(monkeypatch)

    mock_drive_authentication(
        monkeypatch,
        service
    )

    checksum = hashlib.sha256(
        encrypted_path.read_bytes()
    ).hexdigest()

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "calculate_sha256",
        lambda path: checksum
    )

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "find_existing_backup",
        lambda *args: None
    )

    # Return an incorrect size to simulate failed verification.
    service.files.return_value.create.return_value.execute.return_value = {
        "id": "unverified-drive-file",
        "name": VALID_BACKUP_NAME,
        "size": "1",
        "description": f"SHA256:{checksum}",
    }

    with pytest.raises(
        RuntimeError,
        match="size does not match"
    ):

        upload_backup(encrypted_path)

    update_call = service.files.return_value.update

    update_call.assert_called_once()

    assert (
        update_call.call_args.kwargs["fileId"]
        == "unverified-drive-file"
    )

    assert (
        update_call.call_args.kwargs["body"]["trashed"]
        is True
    )


# --------------------------------------------------
# ENCRYPTED GOOGLE DRIVE DOWNLOAD
# --------------------------------------------------

def test_encrypted_download_success(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    encrypted_bytes = encrypted_path.read_bytes()

    checksum = hashlib.sha256(
        encrypted_bytes
    ).hexdigest()

    service = create_mock_drive_service()

    mock_execute_with_retry(monkeypatch)

    mock_drive_authentication(
        monkeypatch,
        service
    )

    service.files.return_value.get.return_value.execute.return_value = {
        "id": "drive-file-123",
        "name": VALID_BACKUP_NAME,
        "size": str(len(encrypted_bytes)),
        "description": f"SHA256:{checksum}",
        "mimeType": "application/octet-stream",
    }

    class FakeDownloader:
        """Simulate Google Drive downloading file content."""

        def __init__(self, output_file, request):
            self.output_file = output_file
            self.done = False

        def next_chunk(self):
            if not self.done:
                self.output_file.write(encrypted_bytes)
                self.done = True

            return None, self.done

    monkeypatch.setattr(
        encrypted_drive,
        "MediaIoBaseDownload",
        FakeDownloader
    )

    monkeypatch.setattr(
        encrypted_drive.legacy_drive,
        "calculate_sha256",
        lambda path: hashlib.sha256(
            Path(path).read_bytes()
        ).hexdigest()
    )

    monkeypatch.setattr(
        encrypted_drive,
        "validate_encrypted_backup",
        lambda path: {
            "authenticated": True,
            "encryption": "AES-256-GCM",
            "tables": 1,
            "insert_statements": 1,
        }
    )

    destination = tmp_path / "downloads" / VALID_BACKUP_NAME

    result = download_backup(
        "drive-file-123",
        destination
    )

    assert result["verified"] is True

    assert result["file_name"] == VALID_BACKUP_NAME

    assert result["size"] == len(encrypted_bytes)

    assert result["sha256"] == checksum

    assert destination.is_file()

    assert destination.read_bytes() == encrypted_bytes

    # Temporary download directory must be removed.
    assert not list(
        destination.parent.glob(
            "encrypted_drive_download_*"
        )
    )


def test_encrypted_download_checksum_mismatch_cleans_temporary_files(
    tmp_path,
    monkeypatch
):

    encrypted_path = create_encrypted_test_backup(
        tmp_path,
        monkeypatch
    )

    encrypted_bytes = encrypted_path.read_bytes()

    service = create_mock_drive_service()

    mock_execute_with_retry(monkeypatch)

    mock_drive_authentication(
        monkeypatch,
        service
    )

    service.files.return_value.get.return_value.execute.return_value = {
        "id": "drive-file-123",
        "name": VALID_BACKUP_NAME,
        "size": str(len(encrypted_bytes)),
        "description": f"SHA256:{'0' * 64}",
        "mimeType": "application/octet-stream",
    }

    class FakeDownloader:
        """Simulate a completed download with incorrect checksum metadata."""

        def __init__(self, output_file, request):
            self.output_file = output_file
            self.done = False

        def next_chunk(self):
            if not self.done:
                self.output_file.write(encrypted_bytes)
                self.done = True

            return None, self.done

    monkeypatch.setattr(
        encrypted_drive,
        "MediaIoBaseDownload",
        FakeDownloader
    )

    destination = tmp_path / "downloads" / VALID_BACKUP_NAME

    with pytest.raises(
        RuntimeError,
        match="SHA-256 mismatch"
    ):

        download_backup(
            "drive-file-123",
            destination
        )

    assert not destination.exists()

    assert not list(
        destination.parent.glob(
            "encrypted_drive_download_*"
        )
    )


def test_encrypted_download_rejects_invalid_destination_before_authentication(
    tmp_path,
    monkeypatch
):

    service = create_mock_drive_service()

    mock_drive_authentication(
        monkeypatch,
        service
    )

    invalid_destination = tmp_path / "backup.enc"

    with pytest.raises(
        ValueError,
        match="timestamped"
    ):

        download_backup(
            "drive-file-123",
            invalid_destination
        )

    # Invalid destinations must be rejected before cloud access.
    encrypted_drive.legacy_drive.authenticate_google_drive = (
        encrypted_drive.legacy_drive.authenticate_google_drive
    )

    service.files.return_value.get.assert_not_called()