import logging
import re
import shutil
import subprocess
import tempfile

from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_backup_database_url

from app.database.backup_encryption import (
    get_encryption_key,
    encrypt_file,
    decrypt_file,
)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BACKUP_DIR = PROJECT_ROOT / "backups"
LOG_DIR = PROJECT_ROOT / "logs"

EXPECTED_DATABASE = "ai_learning_planner"

DUMP_TIMEOUT_SECONDS = 3600

RETENTION_DAYS = 7


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

def configure_logging():
    """Configure file and console logging."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(
                LOG_DIR / "database_backup.log",
                encoding="utf-8"
            ),
            logging.StreamHandler()
        ],
        force=True
    )


# --------------------------------------------------
# MYSQL CREDENTIAL HANDLING
# --------------------------------------------------

def escape_option_value(value: str) -> str:
    """Escape a value for a quoted MySQL option-file entry."""

    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def create_mysql_option_file(url):
    """
    Create a temporary MySQL credentials file.

    Credentials are not exposed in command-line arguments.
    """

    if not url.username or url.password is None:
        raise RuntimeError("Database credentials are missing.")

    lines = [
        "[client]",
        f'user="{escape_option_value(url.username)}"',
        f'password="{escape_option_value(url.password)}"',
        "default-character-set=utf8mb4",
    ]

    if url.host:
        lines.append(
            f'host="{escape_option_value(url.host)}"'
        )

    if url.port:
        lines.append(f"port={url.port}")

    if url.host:
        lines.append("protocol=TCP")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".cnf",
        prefix="mysql_backup_",
        encoding="utf-8",
        delete=False
    ) as temp_file:

        temp_file.write("\n".join(lines) + "\n")

        return Path(temp_file.name)


# --------------------------------------------------
# SQL BACKUP VERIFICATION
# --------------------------------------------------

def verify_backup(path: Path):
    """
    Perform basic integrity checks on a generated SQL dump.

    The file is scanned line by line to avoid loading the
    complete database dump into memory.
    """

    path = Path(path)

    if not path.exists():
        raise RuntimeError("Backup file was not created.")

    size = path.stat().st_size

    if size == 0:
        raise RuntimeError("Backup file is empty.")

    create_count = 0
    insert_count = 0
    completion_marker_found = False

    create_pattern = re.compile(
        rb"CREATE\s+TABLE",
        re.IGNORECASE
    )

    insert_pattern = re.compile(
        rb"INSERT\s+INTO",
        re.IGNORECASE
    )

    with path.open("rb") as backup_file:

        for line in backup_file:

            create_count += len(
                create_pattern.findall(line)
            )

            insert_count += len(
                insert_pattern.findall(line)
            )

            if b"-- Dump completed on" in line:
                completion_marker_found = True

    if create_count == 0:
        raise RuntimeError(
            "No CREATE TABLE statements found."
        )

    if not completion_marker_found:
        raise RuntimeError(
            "MySQL dump completion marker is missing."
        )

    return {
        "size": size,
        "tables": create_count,
        "insert_statements": insert_count,
    }


# --------------------------------------------------
# ENCRYPTED BACKUP VALIDATION
# --------------------------------------------------

def verify_encrypted_backup(path: Path):
    """
    Validate the encrypted backup container.

    Authentication and SQL structure are checked separately
    by decrypting into a temporary verification file.
    """

    from app.database.backup_encryption import (
        MAGIC_HEADER,
        NONCE_SIZE,
        TAG_SIZE,
    )

    path = Path(path)

    if not path.is_file():
        raise RuntimeError(
            "Encrypted backup file was not created."
        )

    size = path.stat().st_size

    minimum_size = (
        len(MAGIC_HEADER)
        + NONCE_SIZE
        + TAG_SIZE
        + 1
    )

    if size < minimum_size:
        raise RuntimeError(
            "Encrypted backup file is incomplete."
        )

    with path.open("rb") as encrypted_file:
        header = encrypted_file.read(
            len(MAGIC_HEADER)
        )

    if header != MAGIC_HEADER:
        raise RuntimeError(
            "Encrypted backup header is invalid."
        )

    return {
        "size": size,
        "format": "AES-256-GCM",
        "authenticated": False,
    }


# --------------------------------------------------
# LOCAL BACKUP RETENTION
# --------------------------------------------------

def apply_retention(
    backup_dir=BACKUP_DIR,
    keep_days=RETENTION_DAYS
):
    """
    Retain encrypted backups from the latest distinct dates.

    Legacy plaintext .sql backups are intentionally ignored.
    They will not be automatically deleted during migration.
    """

    if (
        not isinstance(keep_days, int)
        or isinstance(keep_days, bool)
        or keep_days < 1
    ):
        raise ValueError(
            "keep_days must be an integer of at least 1."
        )

    if not backup_dir.exists():
        logging.info(
            "Backup directory does not exist. Retention skipped."
        )
        return 0

    pattern = re.compile(
        rf"{re.escape(EXPECTED_DATABASE)}_"
        rf"(\d{{8}})_\d{{6}}\.sql\.enc"
    )

    dated_backups = []

    for path in backup_dir.glob(
        f"{EXPECTED_DATABASE}_*.sql.enc"
    ):

        match = pattern.fullmatch(path.name)

        if match:
            dated_backups.append(
                (match.group(1), path)
            )

    available_dates = sorted(
        {date for date, _ in dated_backups},
        reverse=True
    )

    retained_dates = set(
        available_dates[:keep_days]
    )

    deleted = 0

    for date, path in dated_backups:

        if date not in retained_dates:

            try:
                path.unlink()

                logging.info(
                    "Expired encrypted backup deleted: %s",
                    path.name
                )

                deleted += 1

            except OSError:

                logging.warning(
                    "Could not delete expired encrypted backup: %s",
                    path.name,
                    exc_info=True
                )

    logging.info(
        "Encrypted retention completed. "
        "Retained dates: %s; deleted files: %s",
        len(retained_dates),
        deleted
    )

    return deleted


# --------------------------------------------------
# CREATE DATABASE BACKUP
# --------------------------------------------------

def create_backup():
    """
    Create an encrypted MySQL database backup.

    Plaintext SQL is temporary and is removed after:
    1. SQL structure verification.
    2. Encryption.
    3. Successful authenticated decryption.
    4. Verification of the decrypted SQL.

    Only the encrypted .sql.enc file is published.
    """

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    url = make_url(get_backup_database_url())

    if url.drivername != "mysql+pymysql":
        raise RuntimeError(
            "Expected mysql+pymysql database driver."
        )

    if url.database != EXPECTED_DATABASE:
        raise RuntimeError(
            f"Refusing to back up unexpected database: {url.database}"
        )

    mysqldump = shutil.which("mysqldump")

    if not mysqldump:
        raise RuntimeError(
            "mysqldump was not found in PATH."
        )

    # Fail before creating a plaintext dump if the key is invalid.
    encryption_key = get_encryption_key()

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    base_name = (
        f"{EXPECTED_DATABASE}_{timestamp}"
    )

    final_path = (
        BACKUP_DIR / f"{base_name}.sql.enc"
    )

    sql_partial_path = (
        BACKUP_DIR / f"{base_name}.sql.partial"
    )

    encrypted_partial_path = (
        BACKUP_DIR / f"{base_name}.sql.enc.partial"
    )

    verification_path = (
        BACKUP_DIR / f"{base_name}.verify.sql"
    )

    option_file = None

    all_paths = [
        final_path,
        sql_partial_path,
        encrypted_partial_path,
        verification_path,
    ]

    if any(path.exists() for path in all_paths):
        raise RuntimeError(
            "Backup filename already exists."
        )

    logging.info(
        "Starting encrypted database backup."
    )

    logging.info(
        "Database: %s",
        EXPECTED_DATABASE
    )

    try:

        option_file = create_mysql_option_file(url)

        command = [
            mysqldump,
            f"--defaults-extra-file={option_file}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--no-tablespaces",
            "--skip-lock-tables",
            EXPECTED_DATABASE,
        ]

        logging.info(
            "Executing mysqldump."
        )

        with sql_partial_path.open("wb") as output_file:

            result = subprocess.run(
                command,
                stdout=output_file,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=DUMP_TIMEOUT_SECONDS,
                check=False,
            )

        if result.returncode != 0:
            raise RuntimeError(
                "mysqldump failed: "
                + (result.stderr or "Unknown error")
            )

        # Step 1: Verify plaintext SQL structure.
        sql_verification = verify_backup(
            sql_partial_path
        )

        logging.info(
            "Plaintext SQL structure verified."
        )

        # Step 2: Encrypt the SQL dump.
        encryption_result = encrypt_file(
            source=sql_partial_path,
            destination=encrypted_partial_path,
            key=encryption_key,
        )

        logging.info(
            "Backup encryption completed."
        )

        # Step 3: Verify the encrypted container.
        verify_encrypted_backup(
            encrypted_partial_path
        )

        # Step 4: Decrypt into a temporary verification file.
        decryption_result = decrypt_file(
            source=encrypted_partial_path,
            destination=verification_path,
            key=encryption_key,
        )

        # Step 5: Verify decrypted SQL structure again.
        decrypted_verification = verify_backup(
            verification_path
        )

        if (
            decrypted_verification["size"]
            != sql_verification["size"]
        ):
            raise RuntimeError(
                "Decrypted backup size does not match the original SQL dump."
            )

        if (
            decrypted_verification["tables"]
            != sql_verification["tables"]
        ):
            raise RuntimeError(
                "Decrypted backup table count does not match."
            )

        if (
            decrypted_verification["insert_statements"]
            != sql_verification["insert_statements"]
        ):
            raise RuntimeError(
                "Decrypted backup INSERT count does not match."
            )

        # Step 6: Publish the encrypted backup.
        encrypted_partial_path.rename(
            final_path
        )

        logging.info(
            "Encrypted backup published successfully: %s",
            final_path.name
        )

        logging.info(
            "Original SQL size: %s bytes",
            sql_verification["size"]
        )

        logging.info(
            "Encrypted size: %s bytes",
            encryption_result["encrypted_size"]
        )

        logging.info(
            "Tables verified: %s",
            sql_verification["tables"]
        )

        logging.info(
            "INSERT statements verified: %s",
            sql_verification["insert_statements"]
        )

        logging.info(
            "Authenticated decryption verification: SUCCESS"
        )

        # Retention runs only after successful publication.
        try:
            apply_retention()

        except Exception:
            logging.exception(
                "Encrypted backup retention encountered an error."
            )

        return final_path

    except Exception:

        # Never leave the final encrypted name on failure.
        if final_path.exists():
            final_path.unlink(missing_ok=True)

        logging.exception(
            "Encrypted database backup failed."
        )

        raise

    finally:

        # Remove all temporary plaintext and encrypted files.
        for temporary_path in (
            sql_partial_path,
            encrypted_partial_path,
            verification_path,
        ):

            if temporary_path.exists():

                try:
                    temporary_path.unlink()

                except OSError:
                    logging.exception(
                        "Could not remove temporary backup file: %s",
                        temporary_path.name
                    )

        if option_file and option_file.exists():

            try:
                option_file.unlink()

            except OSError:
                logging.exception(
                    "Could not remove temporary MySQL credentials file."
                )


# --------------------------------------------------
# MAIN ENTRY POINT
# --------------------------------------------------

def main():

    configure_logging()

    # Step 1: Create the local encrypted backup.
    try:

        backup_path = create_backup()

        print("\nLOCAL BACKUP RESULT: SUCCESS")
        print("Encrypted backup file:", backup_path)

    except Exception as exc:

        logging.exception(
            "Local encrypted database backup failed."
        )

        print("\nLOCAL BACKUP RESULT: FAILED")
        print("Reason:", exc)

        raise SystemExit(1)

    # Step 2: Upload the verified encrypted backup to Google Drive.
    try:

        from app.database.encrypted_google_drive_backup import upload_backup

        cloud_result = upload_backup(backup_path)
        print("\nCLOUD BACKUP RESULT: SUCCESS")
        print("Google Drive file ID:", cloud_result["file_id"])
        print("Cloud backup filename:", cloud_result["file_name"])
        print("SHA-256:", cloud_result["sha256"])

        if cloud_result.get("already_exists"):
            print("Cloud backup status: Already existed")
        else:
            print("Cloud backup status: Uploaded successfully")

        print("\nBACKUP RESULT: LOCAL AND CLOUD SUCCESS")

    except Exception as exc:

        logging.exception(
            "Encrypted Google Drive backup failed."
        )

        print("\nCLOUD BACKUP RESULT: FAILED")
        print("Reason:", exc)

        print(
            "\nLOCAL BACKUP RESULT: PRESERVED"
        )

        raise SystemExit(2)


if __name__ == "__main__":
    main()
