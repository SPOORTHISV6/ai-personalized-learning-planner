
from unittest.mock import MagicMock

from app.database.google_drive_backup import apply_cloud_retention


def test_cloud_retention_keeps_latest_seven_distinct_dates():

    service = MagicMock()

    files = [
        {
            "id": f"file-{day}",
            "name": f"ai_learning_planner_202611{day:02d}_120000.sql",
            "size": "1024",
            "description": "SHA256:test"
        }
        for day in range(1, 11)
    ]

    service.files.return_value.list.return_value.execute.return_value = {
        "files": files
    }

    result = apply_cloud_retention(
        service,
        "backup-folder-123",
        keep_dates=7
    )

    assert result["total_backups"] == 10
    assert result["retained_dates"] == 7
    assert result["retained_files"] == 7
    assert result["trashed_files"] == 3

    assert service.files.return_value.update.call_count == 3


def test_cloud_retention_keeps_all_files_on_retained_dates():

    service = MagicMock()

    files = [
        {
            "id": "file-1",
            "name": "ai_learning_planner_20261110_080000.sql"
        },
        {
            "id": "file-2",
            "name": "ai_learning_planner_20261110_120000.sql"
        },
        {
            "id": "file-3",
            "name": "ai_learning_planner_20261109_120000.sql"
        }
    ]

    service.files.return_value.list.return_value.execute.return_value = {
        "files": files
    }

    result = apply_cloud_retention(
        service,
        "backup-folder-123",
        keep_dates=2
    )

    assert result["retained_files"] == 3
    assert result["trashed_files"] == 0

    service.files.return_value.update.assert_not_called()


def test_cloud_retention_ignores_unrelated_files():

    service = MagicMock()

    files = [
        {
            "id": "file-1",
            "name": "important_document.pdf"
        },
        {
            "id": "file-2",
            "name": "ai_learning_planner_invalid.sql"
        }
    ]

    service.files.return_value.list.return_value.execute.return_value = {
        "files": files
    }

    result = apply_cloud_retention(
        service,
        "backup-folder-123",
        keep_dates=7
    )

    assert result["total_backups"] == 0
    assert result["trashed_files"] == 0

    service.files.return_value.update.assert_not_called()


def test_cloud_retention_rejects_zero_retention():

    service = MagicMock()

    try:
        apply_cloud_retention(
            service,
            "backup-folder-123",
            keep_dates=0
        )
        assert False, "Expected ValueError"

    except ValueError as exc:
        assert "at least 1" in str(exc)
