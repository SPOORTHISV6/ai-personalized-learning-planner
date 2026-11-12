
import tempfile

from pathlib import Path
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

import app.database.google_drive_backup as drive_backup


# --------------------------------------------------
# TEST CREDENTIAL GENERATOR
# --------------------------------------------------

def create_mock_credentials(refresh_error=None):
    """
    Create mock OAuth credentials.

    No real Google credentials are loaded or modified.
    """

    credentials = MagicMock()

    credentials.expired = True
    credentials.valid = False
    credentials.refresh_token = "temporary-fake-refresh-token"

    if refresh_error:
        credentials.refresh.side_effect = refresh_error

    return credentials


# --------------------------------------------------
# TEST 1: REJECTED REFRESH TOKEN
# --------------------------------------------------

def test_rejected_refresh_token():

    print("\n" + "=" * 55)
    print("TEST 1: REJECTED REFRESH TOKEN")
    print("=" * 55)

    credentials = create_mock_credentials(
        refresh_error=RefreshError(
            "Simulated invalid_grant response"
        )
    )

    with tempfile.TemporaryDirectory() as temp_dir:

        temporary_token = Path(temp_dir) / "test_token.json"

        temporary_token.write_text(
            '{"temporary": "test"}',
            encoding="utf-8"
        )

        with (
            patch.object(
                drive_backup,
                "TOKEN_FILE",
                temporary_token
            ),
            patch.object(
                drive_backup.Credentials,
                "from_authorized_user_file",
                return_value=credentials
            ),
            patch.object(
                drive_backup,
                "save_credentials"
            ) as mock_save,
            patch.object(
                drive_backup.InstalledAppFlow,
                "from_client_secrets_file"
            ) as mock_browser
        ):

            try:

                drive_backup.authenticate_google_drive(
                    allow_browser_auth=False
                )

                raise AssertionError(
                    "Expected authentication to fail, but it succeeded."
                )

            except RuntimeError as exc:

                expected_message = (
                    "refresh token is invalid, expired or revoked"
                )

                message = str(exc)

                print("Expected: Scheduled authentication failure")
                print("Actual:", message)
                print("Browser authentication called:", mock_browser.called)
                print("Credentials saved:", mock_save.called)

                assert expected_message in message, (
                    f"Unexpected authentication error: {message}"
                )

                assert not mock_browser.called, (
                    "Browser authentication should not be triggered."
                )

                assert not mock_save.called, (
                    "Credentials should not be saved after rejected refresh."
                )

                print("Result: PASS")


# --------------------------------------------------
# TEST 2: TEMPORARY NETWORK FAILURE
# --------------------------------------------------

def test_temporary_network_failure():

    print("\n" + "=" * 55)
    print("TEST 2: TEMPORARY NETWORK FAILURE")
    print("=" * 55)

    credentials = create_mock_credentials(
        refresh_error=ConnectionError(
            "Simulated network unavailable"
        )
    )

    with tempfile.TemporaryDirectory() as temp_dir:

        temporary_token = Path(temp_dir) / "test_token.json"

        temporary_token.write_text(
            '{"temporary": "test"}',
            encoding="utf-8"
        )

        with (
            patch.object(
                drive_backup,
                "TOKEN_FILE",
                temporary_token
            ),
            patch.object(
                drive_backup.Credentials,
                "from_authorized_user_file",
                return_value=credentials
            ),
            patch.object(
                drive_backup,
                "save_credentials"
            ) as mock_save,
            patch.object(
                drive_backup.InstalledAppFlow,
                "from_client_secrets_file"
            ) as mock_browser
        ):

            try:

                drive_backup.authenticate_google_drive(
                    allow_browser_auth=False
                )

                raise AssertionError(
                    "Expected network failure to propagate, but authentication succeeded."
                )

            except ConnectionError as exc:

                message = str(exc)

                print("Expected: Network error propagated")
                print("Actual:", message)
                print("Browser authentication called:", mock_browser.called)
                print("Credentials saved:", mock_save.called)

                assert "Simulated network unavailable" in message, (
                    f"Unexpected network error: {message}"
                )

                assert not mock_browser.called, (
                    "Browser authentication should not be triggered."
                )

                assert not mock_save.called, (
                    "Credentials should not be saved after network failure."
                )

                print("Result: PASS")


# --------------------------------------------------
# MAIN TEST SUITE
# --------------------------------------------------

def main():

    tests = [
        test_rejected_refresh_token,
        test_temporary_network_failure,
    ]

    passed = 0
    failed = 0

    print("\nGOOGLE OAUTH AUTHENTICATION TEST SUITE")

    for test_function in tests:
        try:
            test_function()
            passed += 1
        except AssertionError as exc:
            failed += 1
            print("ASSERTION ERROR:", exc)

    total = len(tests)

    print("\n" + "=" * 55)
    print("AUTHENTICATION TEST SUMMARY")
    print("=" * 55)

    print("Total tests:", total)
    print("Passed:", passed)
    print("Failed:", failed)

    if failed:
        raise SystemExit(1)

    print("\nALL AUTHENTICATION TESTS PASSED")


if __name__ == "__main__":
    main()
