
import logging
import re
import shutil
import subprocess
import tempfile

from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_database_url


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BACKUP_DIR = PROJECT_ROOT / "backups"
LOG_DIR = PROJECT_ROOT / "logs"

EXPECTED_DATABASE = "ai_learning_planner"

DUMP_TIMEOUT_SECONDS = 3600

# Keep backups from the latest 7 distinct dates.
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
# BACKUP VERIFICATION
# --------------------------------------------------

def verify_backup(path: Path):
    """
    Perform basic integrity checks on the generated SQL dump.

    Checks:
    1. Backup file exists.
    2. Backup file is not empty.
    3. CREATE TABLE statements exist.
    4. MySQL dump completion marker exists.
    """

    if not path.exists():
        raise RuntimeError("Backup file was not created.")

    size = path.stat().st_size

    if size == 0:
        raise RuntimeError("Backup file is empty.")

    content = path.read_bytes()

    create_count = len(
        re.findall(
            rb"CREATE\s+TABLE",
            content,
            re.IGNORECASE
        )
    )

    insert_count = len(
        re.findall(
            rb"INSERT\s+INTO",
            content,
            re.IGNORECASE
        )
    )

    completion_marker = b"-- Dump completed on"

    if create_count == 0:
        raise RuntimeError(
            "No CREATE TABLE statements found."
        )

    if completion_marker not in content:
        raise RuntimeError(
            "MySQL dump completion marker is missing."
        )

    return {
        "size": size,
        "tables": create_count,
        "insert_statements": insert_count,
    }


# --------------------------------------------------
# BACKUP RETENTION
# --------------------------------------------------

def apply_retention(
    backup_dir=BACKUP_DIR,
    keep_days=RETENTION_DAYS
):
    """
    Retain backups from the latest seven distinct backup dates.

    Multiple backups created on a retained date are preserved.
    Files with unexpected names are ignored.
    """

    if keep_days < 1:
        raise ValueError("keep_days must be at least 1.")

    if not backup_dir.exists():
        logging.info(
            "Backup directory does not exist. Retention skipped."
        )
        return 0

    pattern = re.compile(
        rf"{re.escape(EXPECTED_DATABASE)}_(\d{{8}})_\d{{6}}\.sql"
    )

    dated_backups = []

    for path in backup_dir.glob(
        f"{EXPECTED_DATABASE}_*.sql"
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
                    "Expired backup deleted: %s",
                    path.name
                )

                deleted += 1

            except OSError:

                logging.warning(
                    "Could not delete expired backup: %s",
                    path.name,
                    exc_info=True
                )

    logging.info(
        "Retention completed. Retained backup dates: %s; deleted files: %s",
        len(retained_dates),
        deleted
    )

    return deleted


# --------------------------------------------------
# CREATE DATABASE BACKUP
# --------------------------------------------------

def create_backup():
    """
    Create and verify a timestamped MySQL database backup.

    The final backup filename is published only after
    mysqldump succeeds and verification passes.
    """

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    url = make_url(
        get_database_url()
    )

    # Validate database driver.
    if url.drivername != "mysql+pymysql":

        raise RuntimeError(
            "Expected mysql+pymysql database driver."
        )

    # Validate database name.
    if url.database != EXPECTED_DATABASE:

        raise RuntimeError(
            f"Refusing to back up unexpected database: {url.database}"
        )

    # Locate mysqldump.
    mysqldump = shutil.which("mysqldump")

    if not mysqldump:

        raise RuntimeError(
            "mysqldump was not found in PATH."
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    final_path = (
        BACKUP_DIR /
        f"{EXPECTED_DATABASE}_{timestamp}.sql"
    )

    partial_path = final_path.with_suffix(
        ".sql.partial"
    )

    option_file = None

    if final_path.exists() or partial_path.exists():

        raise RuntimeError(
            "Backup filename already exists."
        )

    logging.info("Starting database backup.")

    logging.info(
        "Database: %s",
        EXPECTED_DATABASE
    )

    try:

        # Create temporary MySQL credentials file.
        option_file = create_mysql_option_file(url)

        # mysqldump command.
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

        # Write dump to a temporary file.
        with partial_path.open("wb") as output_file:

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

        # Check mysqldump result.
        if result.returncode != 0:

            raise RuntimeError(
                "mysqldump failed: "
                + (result.stderr or "Unknown error")
            )

        # Verify generated SQL file.
        verification = verify_backup(
            partial_path
        )

        # Publish only a verified backup.
        partial_path.replace(
            final_path
        )

        logging.info(
            "Backup completed successfully."
        )

        logging.info(
            "File: %s",
            final_path.name
        )

        logging.info(
            "Size: %s bytes",
            verification["size"]
        )

        logging.info(
            "Tables: %s",
            verification["tables"]
        )

        logging.info(
            "INSERT statements: %s",
            verification["insert_statements"]
        )

        # Apply retention after successful backup.
        # Retention failure must not invalidate the backup.
        try:

            apply_retention()

        except Exception:

            logging.exception(
                "Backup retention encountered an error."
            )

        return final_path

    except Exception:

        # Remove incomplete backup.
        if partial_path.exists():

            try:
                partial_path.unlink()

            except OSError:

                logging.exception(
                    "Could not remove incomplete backup file."
                )

        logging.exception(
            "Database backup failed."
        )

        raise

    finally:

        # Remove temporary credentials file.
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

    # ========================================================
    # STEP 1: CREATE LOCAL DATABASE BACKUP
    # ========================================================

    try:

        backup_path = create_backup()

        print("\nLOCAL BACKUP RESULT: SUCCESS")
        print("Backup file:", backup_path)

    except Exception as exc:

        logging.exception("Local database backup failed.")

        print("\nLOCAL BACKUP RESULT: FAILED")
        print("Reason:", exc)

        raise SystemExit(1)

    # ========================================================
    # STEP 2: UPLOAD BACKUP TO GOOGLE DRIVE
    # ========================================================

    try:

        from app.database.google_drive_backup import upload_backup

        cloud_result = upload_backup(backup_path)

        logging.info(
            "Google Drive backup completed: %s",
            cloud_result["file_name"]
        )

        print("\nCLOUD BACKUP RESULT: SUCCESS")
        print("Drive file:", cloud_result["file_name"])
        print("Drive file ID:", cloud_result["file_id"])
        print("SHA256:", cloud_result["sha256"])

        # Use .get() so older test mocks or optional fields
        # do not cause KeyError.
        retention_result = cloud_result.get("cloud_retention")

        if retention_result is not None:
            print("Cloud retention:", retention_result)
        else:
            print("Cloud retention: Not reported")

        already_exists = cloud_result.get(
            "already_exists",
            False
        )

        if already_exists:
            print("Upload status: Existing identical backup reused.")
        else:
            print("Upload status: New backup uploaded.")

        print("\nBACKUP RESULT: LOCAL AND CLOUD SUCCESS")

    except Exception as exc:

        logging.exception(
            "Google Drive upload failed. "
            "The verified local backup remains available."
        )

        print("\nCLOUD BACKUP RESULT: FAILED")
        print("Reason:", exc)
        print("LOCAL BACKUP RESULT: SUCCESS")

        # Exit code 2 means local backup succeeded,
        # but cloud backup or its retention operation failed.
        raise SystemExit(2)


if __name__ == "__main__":
    main()
