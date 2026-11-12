
import tempfile

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from google.oauth2.credentials import Credentials

import app.database.google_drive_backup as drive_backup


# --------------------------------------------------
# TEST CREDENTIAL GENERATOR
# --------------------------------------------------

def create_test_credentials(
    refresh_token=None,
    expired=False
):
    """
    Generate temporary OAuth credentials.

    These credentials are used only for testing.
    The real token.json file is never modified.
    """

    expiry = (
        datetime.now(timezone.utc) - timedelta(days=1)
        if expired
        else datetime.now(timezone.utc) + timedelta(hours=1)
    )

    credentials = Credentials(
        token="temporary-test-access-token",
        refresh_token=refresh_token or "",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="temporary-client-id",
        client_secret="temporary-client-secret",
        scopes=drive_backup.SCOPES,
        expiry=expiry,
    )

    return credentials.to_json()


# --------------------------------------------------
# GENERIC TEST RUNNER
# --------------------------------------------------

def run_test(
    name,
    expected_status,
    token_content=None
):
    """
    Execute one OAuth health test using a temporary token file.
    """

    with tempfile.TemporaryDirectory() as temp_dir:

        temporary_token = Path(temp_dir) / "test_token.json"

        if token_content is not None:
            temporary_token.write_text(
                token_content,
                encoding="utf-8"
            )

        with patch.object(
            drive_backup,
            "TOKEN_FILE",
            temporary_token
        ):

            result = drive_backup.check_oauth_health()

        actual_status = result["status"]

        passed = actual_status == expected_status

        print(f"\nTEST: {name}")
        print("Expected:", expected_status)
        print("Actual:", actual_status)
        print("Result:", "PASS" if passed else "FAIL")

        return passed


# --------------------------------------------------
# MAIN TEST SUITE
# --------------------------------------------------

def main():

    results = []

    print("=" * 55)
    print("GOOGLE OAUTH HEALTH TEST SUITE")
    print("=" * 55)

    # TEST 1: Missing token file.
    results.append(
        run_test(
            name="Missing token file",
            expected_status="TOKEN_MISSING"
        )
    )

    # TEST 2: Malformed token file.
    results.append(
        run_test(
            name="Malformed token file",
            expected_status="TOKEN_INVALID",
            token_content="{ invalid json"
        )
    )

    # TEST 3: Valid access token.
    results.append(
        run_test(
            name="Valid access token",
            expected_status="HEALTHY",
            token_content=create_test_credentials(
                refresh_token="temporary-refresh-token",
                expired=False
            )
        )
    )

    # TEST 4: Expired access token with refresh token.
    results.append(
        run_test(
            name="Expired access token with refresh token",
            expected_status="REFRESH_REQUIRED",
            token_content=create_test_credentials(
                refresh_token="temporary-refresh-token",
                expired=True
            )
        )
    )

    # TEST 5: Expired access token without refresh token.
    results.append(
        run_test(
            name="Expired access token without refresh token",
            expected_status="REAUTH_REQUIRED",
            token_content=create_test_credentials(
                refresh_token=None,
                expired=True
            )
        )
    )

    # --------------------------------------------------
    # TEST SUMMARY
    # --------------------------------------------------

    passed = sum(results)
    total = len(results)
    failed = total - passed

    print("\n" + "=" * 55)
    print("OAUTH HEALTH TEST SUMMARY")
    print("=" * 55)

    print(f"Total tests : {total}")
    print(f"Passed      : {passed}")
    print(f"Failed      : {failed}")

    if failed > 0:
        print("\nSOME OAUTH HEALTH TESTS FAILED")
        raise SystemExit(1)

    print("\nALL OAUTH HEALTH TESTS PASSED")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    main()
