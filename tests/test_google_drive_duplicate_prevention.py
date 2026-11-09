
import pytest
from unittest.mock import MagicMock

from app.database.google_drive_backup import find_existing_backup


def test_find_existing_backup_returns_matching_file():

    service = MagicMock()

    expected_file = {
        "id": "drive-file-123",
        "name": "backup.sql",
        "size": "1024",
        "description": "SHA256:abc123",
        "parents": ["backup-folder-123"]
    }

    service.files.return_value.list.return_value.execute.return_value = {
        "files": [expected_file]
    }

    result = find_existing_backup(
        service,
        "backup-folder-123",
        "backup.sql"
    )

    assert result == expected_file


def test_find_existing_backup_returns_none_when_missing():

    service = MagicMock()

    service.files.return_value.list.return_value.execute.return_value = {
        "files": []
    }

    result = find_existing_backup(
        service,
        "backup-folder-123",
        "backup.sql"
    )

    assert result is None


def test_find_existing_backup_rejects_multiple_matches():

    service = MagicMock()

    service.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "file-1",
                "name": "backup.sql"
            },
            {
                "id": "file-2",
                "name": "backup.sql"
            }
        ]
    }

    with pytest.raises(
        RuntimeError,
        match="Multiple Google Drive backups"
    ):

        find_existing_backup(
            service,
            "backup-folder-123",
            "backup.sql"
        )
