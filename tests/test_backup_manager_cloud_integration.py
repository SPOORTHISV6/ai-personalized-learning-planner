import pytest

from app.database import backup_manager
from app.database import google_drive_backup


def test_local_and_cloud_backup_success(monkeypatch, capsys, tmp_path):
    backup_file = tmp_path / "test_backup.sql"
    backup_file.write_text("test backup")

    monkeypatch.setattr(
        backup_manager,
        "configure_logging",
        lambda: None
    )

    monkeypatch.setattr(
        backup_manager,
        "create_backup",
        lambda: backup_file
    )

    monkeypatch.setattr(
        google_drive_backup,
        "upload_backup",
        lambda path: {
            "file_id": "test-drive-id",
            "file_name": path.name,
            "sha256": "test-checksum"
        }
    )

    backup_manager.main()

    output = capsys.readouterr().out

    assert "LOCAL BACKUP RESULT: SUCCESS" in output
    assert "CLOUD BACKUP RESULT: SUCCESS" in output
    assert "BACKUP RESULT: LOCAL AND CLOUD SUCCESS" in output


def test_cloud_failure_preserves_local_backup(
    monkeypatch,
    capsys,
    tmp_path
):
    backup_file = tmp_path / "test_backup.sql"
    backup_file.write_text("test backup")

    monkeypatch.setattr(
        backup_manager,
        "configure_logging",
        lambda: None
    )

    monkeypatch.setattr(
        backup_manager,
        "create_backup",
        lambda: backup_file
    )

    def fail_upload(path):
        raise RuntimeError("Simulated Google Drive failure")

    monkeypatch.setattr(
        google_drive_backup,
        "upload_backup",
        fail_upload
    )

    with pytest.raises(SystemExit) as exc:
        backup_manager.main()

    assert exc.value.code == 2
    assert backup_file.exists()

    output = capsys.readouterr().out

    assert "LOCAL BACKUP RESULT: SUCCESS" in output
    assert "CLOUD BACKUP RESULT: FAILED" in output


def test_local_failure_skips_cloud_upload(
    monkeypatch,
    capsys
):
    monkeypatch.setattr(
        backup_manager,
        "configure_logging",
        lambda: None
    )

    def fail_backup():
        raise RuntimeError("Simulated local backup failure")

    monkeypatch.setattr(
        backup_manager,
        "create_backup",
        fail_backup
    )

    def unexpected_upload(path):
        pytest.fail("Cloud upload must not run after local failure")

    monkeypatch.setattr(
        google_drive_backup,
        "upload_backup",
        unexpected_upload
    )

    with pytest.raises(SystemExit) as exc:
        backup_manager.main()

    assert exc.value.code == 1

    output = capsys.readouterr().out

    assert "LOCAL BACKUP RESULT: FAILED" in output
