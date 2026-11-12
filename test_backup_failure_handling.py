
import tempfile

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.database import backup_manager
from app.database import google_drive_backup


# --------------------------------------------------
# TEST 1: CLOUD FAILURE, LOCAL BACKUP PRESERVED
# --------------------------------------------------

def test_cloud_failure_preserves_local_backup():

    print("\n" + "=" * 60)
    print("TEST 1: CLOUD FAILURE, LOCAL BACKUP PRESERVED")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:

        backup_path = Path(temp_dir) / "ai_learning_planner_test.sql"

        backup_path.write_text(
            "-- Simulated verified SQL backup\n",
            encoding="utf-8"
        )

        output = StringIO()

        with (
            patch.object(backup_manager, "configure_logging"),
            patch.object(
                backup_manager,
                "create_backup",
                return_value=backup_path
            ) as mock_create_backup,
            patch.object(
                google_drive_backup,
                "check_oauth_health",
                return_value={
                    "status": "REAUTH_REQUIRED",
                    "token_file_exists": True,
                    "refresh_token_present": False,
                    "access_token_valid": False,
                    "message": "Manual authentication required."
                }
            ),
            patch.object(
                google_drive_backup,
                "upload_backup",
                side_effect=RuntimeError(
                    "Simulated Google Drive authentication failure"
                )
            ) as mock_upload
        ):

            try:
                with redirect_stdout(output):
                    backup_manager.main()

                exit_code = 0

            except SystemExit as exc:
                exit_code = exc.code

        captured_output = output.getvalue()

        checks = {
            "Local backup creation attempted":
                mock_create_backup.called,

            "Cloud upload attempted":
                mock_upload.called,

            "Local backup still exists":
                backup_path.exists(),

            "Exit code is 2":
                exit_code == 2,

            "Local backup success reported":
                "LOCAL BACKUP RESULT: SUCCESS" in captured_output,

            "Cloud backup failure reported":
                "CLOUD BACKUP RESULT: FAILED" in captured_output,
        }

        for name, passed in checks.items():
            print(f"{name}:", "PASS" if passed else "FAIL")

        print("Actual exit code:", exit_code)
        print("\nCaptured workflow output:")
        print(captured_output)

        all_passed = all(checks.values())

        print("\nTEST RESULT:", "PASS" if all_passed else "FAIL")

        assert all_passed, (
            f"Cloud failure handling checks failed: {checks}"
        )


# --------------------------------------------------
# TEST 2: LOCAL BACKUP FAILURE STOPS CLOUD UPLOAD
# --------------------------------------------------

def test_local_failure_stops_cloud_upload():

    print("\n" + "=" * 60)
    print("TEST 2: LOCAL BACKUP FAILURE STOPS CLOUD UPLOAD")
    print("=" * 60)

    output = StringIO()

    with (
        patch.object(backup_manager, "configure_logging"),
        patch.object(
            backup_manager,
            "create_backup",
            side_effect=RuntimeError(
                "Simulated MySQL backup failure"
            )
        ),
        patch.object(
            google_drive_backup,
            "upload_backup"
        ) as mock_upload
    ):

        try:
            with redirect_stdout(output):
                backup_manager.main()

            exit_code = 0

        except SystemExit as exc:
            exit_code = exc.code

    captured_output = output.getvalue()

    checks = {
        "Exit code is 1":
            exit_code == 1,

        "Local backup failure reported":
            "LOCAL BACKUP RESULT: FAILED" in captured_output,

        "Cloud upload was not attempted":
            not mock_upload.called,
    }

    for name, passed in checks.items():
        print(f"{name}:", "PASS" if passed else "FAIL")

    print("Actual exit code:", exit_code)

    all_passed = all(checks.values())

    print("\nTEST RESULT:", "PASS" if all_passed else "FAIL")

    assert all_passed, (
        f"Local failure handling checks failed: {checks}"
    )


# --------------------------------------------------
# MAIN TEST SUITE
# --------------------------------------------------

def main():

    tests = [
        test_cloud_failure_preserves_local_backup,
        test_local_failure_stops_cloud_upload,
    ]

    passed = 0
    failed = 0

    print("\nDATABASE BACKUP FAILURE HANDLING TESTS")

    for test_function in tests:
        try:
            test_function()
            passed += 1
        except AssertionError as exc:
            failed += 1
            print("ASSERTION ERROR:", exc)

    total = len(tests)

    print("\n" + "=" * 60)
    print("BACKUP FAILURE HANDLING SUMMARY")
    print("=" * 60)

    print("Total tests:", total)
    print("Passed:", passed)
    print("Failed:", failed)

    if failed:
        raise SystemExit(1)

    print("\nALL BACKUP FAILURE HANDLING TESTS PASSED")


if __name__ == "__main__":
    main()
