import pytest

from app.database import backup_manager
from app.database import encrypted_google_drive_backup


# --------------------------------------------------
# LOCAL AND CLOUD BACKUP SUCCESS
# --------------------------------------------------

def test_local_and_cloud_backup_success(
    monkeypatch,
    capsys,
    tmp_path
):

    backup_file = (
        tmp_path / "ai_learning_planner_20261114_120000.sql.enc"
    )

    backup_file.write_bytes(b"encrypted backup test data")

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

    upload_mock = []

    def mock_upload(path):

        upload_mock.append(path)

        return {
            "file_id": "test-drive-id",
            "file_name": path.name,
            "sha256": "test-checksum",
            "already_exists": False,
        }

    monkeypatch.setattr(
        encrypted_google_drive_backup,
        "upload_backup",
        mock_upload
    )

    backup_manager.main()

    output = capsys.readouterr().out

    assert "LOCAL BACKUP RESULT: SUCCESS" in output

    assert "CLOUD BACKUP RESULT: SUCCESS" in output

    assert "BACKUP RESULT: LOCAL AND CLOUD SUCCESS" in output

    assert "test-drive-id" in output

    assert len(upload_mock) == 1

    assert upload_mock[0] == backup_file

    assert backup_file.exists()


# --------------------------------------------------
# CLOUD FAILURE PRESERVES LOCAL BACKUP
# --------------------------------------------------

def test_cloud_failure_preserves_local_backup(
    monkeypatch,
    capsys,
    tmp_path
):

    backup_file = (
        tmp_path / "ai_learning_planner_20261114_120000.sql.enc"
    )

    backup_file.write_bytes(b"encrypted backup test data")

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

        raise RuntimeError(
            "Simulated Google Drive failure"
        )

    monkeypatch.setattr(
        encrypted_google_drive_backup,
        "upload_backup",
        fail_upload
    )

    with pytest.raises(SystemExit) as exc:

        backup_manager.main()

    assert exc.value.code == 2

    assert backup_file.exists()

    assert backup_file.read_bytes() == b"encrypted backup test data"

    output = capsys.readouterr().out

    assert "LOCAL BACKUP RESULT: SUCCESS" in output

    assert "CLOUD BACKUP RESULT: FAILED" in output

    assert "LOCAL BACKUP RESULT: PRESERVED" in output


# --------------------------------------------------
# LOCAL FAILURE SKIPS CLOUD UPLOAD
# --------------------------------------------------

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

        raise RuntimeError(
            "Simulated local backup failure"
        )

    monkeypatch.setattr(
        backup_manager,
        "create_backup",
        fail_backup
    )

    def unexpected_upload(path):

        pytest.fail(
            "Cloud upload must not run after local failure"
        )

    monkeypatch.setattr(
        encrypted_google_drive_backup,
        "upload_backup",
        unexpected_upload
    )

    with pytest.raises(SystemExit) as exc:

        backup_manager.main()

    assert exc.value.code == 1

    output = capsys.readouterr().out

    assert "LOCAL BACKUP RESULT: FAILED" in output

    assert "CLOUD BACKUP RESULT: SUCCESS" not in output