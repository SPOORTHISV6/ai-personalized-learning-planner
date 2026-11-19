
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_restore_database_url
from app.database.backup_encryption import (
    decrypt_file,
    get_encryption_key,
)
from app.database.backup_manager import (
    create_mysql_option_file,
    verify_backup,
)
from app.database.encrypted_google_drive_backup import (
    download_backup,
)


logger = logging.getLogger(__name__)

EXPECTED_RESTORE_DATABASE = "ai_learning_planner_restore_test"

RESTORE_CONFIRMATION = "RESTORE_TO_TEST_DATABASE"

RESTORE_TIMEOUT_SECONDS = 3600


def validate_restore_target():
    """Allow restoration only into the dedicated restore database."""

    database_url = get_restore_database_url()
    parsed_url = make_url(database_url)

    if parsed_url.drivername != "mysql+pymysql":
        raise RuntimeError(
            "Restore requires the mysql+pymysql driver."
        )

    if parsed_url.database != EXPECTED_RESTORE_DATABASE:
        raise RuntimeError(
            "Unsafe restore target. Restoration is restricted to "
            f"{EXPECTED_RESTORE_DATABASE}."
        )

    if parsed_url.database in {
        "ai_learning_planner",
        "ai_learning_planner_test",
    }:
        raise RuntimeError(
            "Refusing to restore into a protected database."
        )

    return parsed_url

def _mask_sql_comments_and_literals(sql: bytes) -> bytes:
    """
    Mask ordinary comments and quoted values while preserving
    MySQL executable-comment contents.

    This allows security checks to detect commands executed
    through /*!version ... */ comments without falsely matching
    text inside SQL strings or ordinary comments.
    """

    result = bytearray()
    i = 0
    length = len(sql)

    while i < length:
        char = sql[i]

        # Mask quoted strings and backtick identifiers.
        if char in (ord("'"), ord('"'), ord("`")):
            quote = char
            result.append(ord(" "))
            i += 1

            while i < length:
                current = sql[i]

                if current == ord("\\") and quote != ord("`"):
                    result.append(ord(" "))
                    i += 1

                    if i < length:
                        result.append(
                            ord("\n") if sql[i] == ord("\n")
                            else ord(" ")
                        )
                        i += 1
                    continue

                if current == quote:
                    result.append(ord(" "))
                    i += 1

                    # SQL supports doubled quote escaping.
                    if i < length and sql[i] == quote:
                        result.append(ord(" "))
                        i += 1
                        continue

                    break

                result.append(
                    ord("\n") if current == ord("\n")
                    else ord(" ")
                )
                i += 1

            continue

        # Handle block comments.
        if sql[i:i + 2] == b"/*":
            comment_end = sql.find(b"*/", i + 2)

            if comment_end == -1:
                raise RuntimeError(
                    "SQL dump contains an unterminated block comment."
                )

            comment_body = sql[i + 2:comment_end]

            # MySQL executable comments: /*!version SQL */
            if comment_body.startswith(b"!"):
                executable_body = comment_body[1:]

                # Remove optional MySQL version prefix.
                executable_body = re.sub(
                    rb"^\s*\d{5,6}\s*",
                    b"",
                    executable_body,
                    count=1,
                )

                result.extend(b" ")
                result.extend(
                    _mask_sql_comments_and_literals(
                        executable_body
                    )
                )
                result.extend(b" ")

            else:
                # Ordinary comments cannot execute SQL.
                result.extend(
                    b"\n" if byte == ord("\n") else b" "
                    for byte in sql[i:comment_end + 2]
                )

            i = comment_end + 2
            continue

        # Handle MySQL # line comments.
        if char == ord("#"):
            while i < length and sql[i] != ord("\n"):
                result.append(ord(" "))
                i += 1

            continue

        # Handle MySQL -- comments.
        # MySQL requires whitespace or a control character after --.
        if (
            sql[i:i + 2] == b"--"
            and (
                i + 2 == length
                or sql[i + 2] <= 32
            )
        ):
            while i < length and sql[i] != ord("\n"):
                result.append(ord(" "))
                i += 1

            continue

        result.append(char)
        i += 1

    return bytes(result)


def validate_restore_sql(sql_path: Path) -> dict:
    """
    Validate the SQL dump and prevent database-level redirection.

    Detects forbidden commands in normal SQL and MySQL executable
    comments while ignoring quoted strings and ordinary comments.
    """

    verification = verify_backup(sql_path)

    sql_content = sql_path.read_bytes()

    sanitized_sql = _mask_sql_comments_and_literals(
        sql_content
    )

    forbidden_pattern = re.compile(
        rb"(?:^|;)\s*"
        rb"(?:(?:CREATE|DROP)\s+DATABASE\b|USE\s+)",
        re.IGNORECASE,
    )

    match = forbidden_pattern.search(sanitized_sql)

    if match:
        line_number = (
            sanitized_sql[:match.start()].count(b"\n") + 1
        )

        raise RuntimeError(
            "SQL dump contains a database-level command "
            f"at line {line_number}. Restore aborted."
        )

    return verification





def check_restore_connection(database_url) -> dict:
    """Verify the restore account connects to the intended database."""

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT DATABASE()")
            ).scalar()

            mysql_user = connection.execute(
                text("SELECT CURRENT_USER()")
            ).scalar()

        if database_name != EXPECTED_RESTORE_DATABASE:
            raise RuntimeError(
                "Connected database does not match the permitted "
                "restore database."
            )

        return {
            "database": database_name,
            "mysql_user": mysql_user,
        }

    finally:
        engine.dispose()


def restore_backup_from_drive(
    file_id: str,
    confirmation: str,
) -> dict:
    """
    Restore an authenticated encrypted Google Drive backup.

    Restoration is strictly limited to the dedicated test database.
    Existing tables in that database may be replaced by the dump.
    """

    if confirmation != RESTORE_CONFIRMATION:
        raise ValueError(
            "Restore confirmation is missing or incorrect."
        )

    database_url = validate_restore_target()

    connection_result = check_restore_connection(
        database_url
    )

    mysql_client = shutil.which("mysql")

    if not mysql_client:
        raise RuntimeError(
            "MySQL client was not found in PATH."
        )

    encryption_key = get_encryption_key()

    option_file = None

    try:
        with tempfile.TemporaryDirectory(
            prefix="ai_learning_restore_"
        ) as temporary_directory:

            temporary_dir = Path(temporary_directory).resolve()

            sql_path = (
                temporary_dir
                / "ai_learning_planner_restore.sql"
            )

            # Step 1: Download and authenticate the cloud backup.
            # The actual filename is obtained from Google Drive metadata.
            download_result = download_backup(
                file_id=file_id,
                destination=temporary_dir,
            )

            if not download_result.get("verified"):
                raise RuntimeError(
                    "Cloud backup verification did not succeed."
                )

            # Resolve the exact downloaded file path.
            encrypted_path = Path(
                download_result["destination"]
            ).resolve()

            # Verify that the downloaded file is inside our temporary
            # directory and its name matches the validated Drive metadata.
            if (
                encrypted_path.parent != temporary_dir
                or encrypted_path.name
                != download_result.get("file_name")
            ):
                raise RuntimeError(
                    "Downloaded backup path does not match "
                    "validated metadata."
                )

            # Step 2: Decrypt the authenticated backup.
            decryption_result = decrypt_file(
                source=encrypted_path,
                destination=sql_path,
                key=encryption_key,
            )

            # Step 3: Validate SQL before importing.
            sql_verification = validate_restore_sql(
                sql_path
            )

            if (
                decryption_result["decrypted_size"]
                != sql_verification["size"]
            ):
                raise RuntimeError(
                    "Decrypted SQL size verification failed."
                )

            # Step 4: Create temporary MySQL credentials.
            option_file = create_mysql_option_file(
                database_url
            )

            # Step 5: Import only into the validated restore database.
            command = [
                mysql_client,
                f"--defaults-extra-file={option_file}",
                "--database",
                EXPECTED_RESTORE_DATABASE,
            ]

            logger.info(
                "Starting restore into dedicated test database."
            )

            with sql_path.open("rb") as sql_input:
                result = subprocess.run(
                    command,
                    stdin=sql_input,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=RESTORE_TIMEOUT_SECONDS,
                    check=False,
                )

            if result.returncode != 0:
                error_message = result.stderr.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                raise RuntimeError(
                    "MySQL restore failed: "
                    + (error_message or "Unknown MySQL error")
                )

            logger.info(
                "Database restore completed successfully."
            )

            return {
                "status": "SUCCESS",
                "database": EXPECTED_RESTORE_DATABASE,
                "mysql_user": connection_result["mysql_user"],
                "backup_file": download_result["file_name"],
                "backup_sha256": download_result["sha256"],
                "encryption": "AES-256-GCM",
                "authenticated": True,
                "decrypted_size": decryption_result[
                    "decrypted_size"
                ],
                "tables_in_dump": sql_verification["tables"],
                "insert_statements": sql_verification[
                    "insert_statements"
                ],
            }

    finally:
        if option_file and option_file.exists():
            option_file.unlink(missing_ok=True)


if __name__ == "__main__":
    print(
        "Restore manager loaded. "
        "Call restore_backup_from_drive() explicitly to restore."
    )
