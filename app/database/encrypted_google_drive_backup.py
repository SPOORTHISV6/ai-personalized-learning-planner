
import logging
import re
import tempfile

from datetime import datetime
from pathlib import Path

from googleapiclient.http import (
    MediaFileUpload,
    MediaIoBaseDownload,
)

from app.database import google_drive_backup as legacy_drive
from app.database.backup_encryption import (
    decrypt_file,
    get_encryption_key,
)
from app.database.backup_manager import (
    verify_backup,
    verify_encrypted_backup,
)


logger = logging.getLogger(__name__)

CLOUD_RETENTION_DATES = 7

BACKUP_FILENAME_PATTERN = re.compile(
    r"^ai_learning_planner_(\d{8})_(\d{6})\.sql\.enc$"
)


# --------------------------------------------------
# ENCRYPTED BACKUP VALIDATION
# --------------------------------------------------

def validate_encrypted_backup(file_path: Path) -> dict:
    """
    Validate an encrypted backup.

    Checks:
    1. Expected encrypted backup filename.
    2. Encrypted container header and size.
    3. AES-GCM authentication.
    4. Decrypted SQL structure.

    Plaintext verification data is temporary and deleted.
    """

    file_path = Path(file_path).resolve()

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Encrypted backup not found: {file_path}"
        )

    if not BACKUP_FILENAME_PATTERN.fullmatch(file_path.name):
        raise ValueError(
            "Backup filename must match the expected "
            "timestamped .sql.enc format."
        )

    container_result = verify_encrypted_backup(file_path)

    key = get_encryption_key()

    with tempfile.TemporaryDirectory(
        prefix="encrypted_backup_verify_"
    ) as temporary_directory:

        plaintext_path = (
            Path(temporary_directory) / "verification.sql"
        )

        decryption_result = decrypt_file(
            source=file_path,
            destination=plaintext_path,
            key=key,
        )

        sql_result = verify_backup(plaintext_path)

    return {
        "encrypted_size": container_result["size"],
        "decrypted_size": sql_result["size"],
        "tables": sql_result["tables"],
        "insert_statements": sql_result["insert_statements"],
        "encryption": "AES-256-GCM",
        "authenticated": True,
        "decrypted_size_verified": (
            decryption_result["decrypted_size"]
            == sql_result["size"]
        ),
    }


# --------------------------------------------------
# CLOUD RETENTION
# --------------------------------------------------

def apply_encrypted_cloud_retention(
    service,
    folder_id: str,
    keep_dates: int = CLOUD_RETENTION_DATES,
) -> dict:
    """
    Retain encrypted backups from the latest distinct dates.

    Only timestamped .sql.enc files are considered.
    Legacy plaintext .sql backups are ignored.

    Expired encrypted backups are moved to Google Drive trash,
    not permanently deleted.
    """

    if (
        not isinstance(keep_dates, int)
        or isinstance(keep_dates, bool)
        or keep_dates < 1
    ):
        raise ValueError(
            "keep_dates must be an integer of at least 1."
        )

    backups = []
    page_token = None

    while True:

        response = legacy_drive.execute_with_retry(
            service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces="drive",
                fields=(
                    "nextPageToken, "
                    "files(id, name, size, description)"
                ),
                pageSize=100,
                pageToken=page_token,
            ),
            operation_name="List encrypted cloud backups",
        )

        for cloud_file in response.get("files", []):

            file_name = cloud_file.get("name", "")

            match = BACKUP_FILENAME_PATTERN.fullmatch(
                file_name
            )

            if not match:
                continue

            try:
                backup_datetime = datetime.strptime(
                    f"{match.group(1)}_{match.group(2)}",
                    "%Y%m%d_%H%M%S",
                )

            except ValueError:
                logger.warning(
                    "Ignoring invalid encrypted backup timestamp: %s",
                    file_name,
                )
                continue

            backups.append({
                "id": cloud_file["id"],
                "name": file_name,
                "date": backup_datetime.date(),
            })

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    distinct_dates = sorted(
        {backup["date"] for backup in backups},
        reverse=True,
    )

    retained_dates = set(
        distinct_dates[:keep_dates]
    )

    retained_count = 0
    trashed_count = 0

    for backup in backups:

        if backup["date"] in retained_dates:
            retained_count += 1
            continue

        legacy_drive.execute_with_retry(
            service.files().update(
                fileId=backup["id"],
                body={"trashed": True},
                fields="id,name,trashed",
            ),
            operation_name=(
                f"Move expired encrypted backup to trash: "
                f"{backup['name']}"
            ),
        )

        logger.info(
            "Expired encrypted cloud backup moved to trash: %s",
            backup["name"],
        )

        trashed_count += 1

    result = {
        "total_backups": len(backups),
        "retained_dates": len(retained_dates),
        "retained_files": retained_count,
        "trashed_files": trashed_count,
    }

    logger.info(
        "Encrypted cloud retention completed: %s",
        result,
    )

    return result


# --------------------------------------------------
# GOOGLE DRIVE ENCRYPTED UPLOAD
# --------------------------------------------------

def upload_backup(file_path: Path) -> dict:
    """
    Upload an authenticated encrypted backup to Google Drive.

    Includes:
    - Encrypted backup validation.
    - AES-GCM authentication.
    - SHA-256 calculation.
    - Duplicate prevention.
    - Upload metadata verification.
    - Cleanup of unverified cloud uploads.
    - Encrypted cloud retention.
    """

    file_path = Path(file_path).resolve()

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Backup file not found: {file_path}"
        )

    file_size = file_path.stat().st_size

    if file_size == 0:
        raise ValueError(
            "Cannot upload an empty encrypted backup."
        )

    local_verification = validate_encrypted_backup(
        file_path
    )

    checksum = legacy_drive.calculate_sha256(
        file_path
    )

    service = legacy_drive.authenticate_google_drive()

    folder_id = legacy_drive.get_or_create_backup_folder(
        service
    )

    existing_file = legacy_drive.find_existing_backup(
        service,
        folder_id,
        file_path.name,
    )

    if existing_file:

        existing_size = int(
            existing_file.get("size", -1)
        )

        existing_description = existing_file.get(
            "description",
            "",
        )

        expected_description = f"SHA256:{checksum}"

        if (
            existing_size == file_size
            and expected_description in existing_description
        ):

            retention_result = apply_encrypted_cloud_retention(
                service,
                folder_id,
                keep_dates=CLOUD_RETENTION_DATES,
            )

            logger.info(
                "Identical encrypted cloud backup already exists: %s",
                file_path.name,
            )

            return {
                "file_id": existing_file["id"],
                "file_name": existing_file["name"],
                "size": existing_size,
                "sha256": checksum,
                "local_verification": local_verification,
                "already_exists": True,
                "cloud_retention": retention_result,
            }

        raise RuntimeError(
            "A cloud backup with the same filename already exists, "
            "but its size or checksum differs. "
            "The existing backup was not modified."
        )

    metadata = {
        "name": file_path.name,
        "parents": [folder_id],
        "description": f"SHA256:{checksum}",
    }

    media = MediaFileUpload(
        str(file_path),
        mimetype="application/octet-stream",
        resumable=True,
    )

    uploaded_file = None

    try:

        # Uploads are deliberately not blindly retried.
        # Duplicate detection handles uncertain upload outcomes.
        uploaded_file = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name,size,description,parents",
        ).execute()

        if not uploaded_file.get("id"):
            raise RuntimeError(
                "Google Drive did not return an uploaded file ID."
            )

        uploaded_size = int(
            uploaded_file.get("size", -1)
        )

        if uploaded_size != file_size:
            raise RuntimeError(
                "Uploaded encrypted backup size does not match "
                "the local file."
            )

        uploaded_description = uploaded_file.get(
            "description",
            "",
        )

        if f"SHA256:{checksum}" not in uploaded_description:
            raise RuntimeError(
                "Uploaded encrypted backup checksum metadata "
                "does not match."
            )

    except Exception:

        if uploaded_file and uploaded_file.get("id"):

            try:
                legacy_drive.execute_with_retry(
                    service.files().update(
                        fileId=uploaded_file["id"],
                        body={"trashed": True},
                        fields="id,name,trashed",
                    ),
                    operation_name=(
                        f"Move unverified upload to trash: "
                        f"{file_path.name}"
                    ),
                )

            except Exception:
                logger.exception(
                    "Could not clean up unverified cloud upload."
                )

        logger.exception(
            "Encrypted Google Drive upload failed: %s",
            file_path.name,
        )

        raise

    retention_result = apply_encrypted_cloud_retention(
        service,
        folder_id,
        keep_dates=CLOUD_RETENTION_DATES,
    )

    logger.info(
        "Encrypted cloud backup uploaded successfully: %s",
        file_path.name,
    )

    return {
        "file_id": uploaded_file["id"],
        "file_name": uploaded_file["name"],
        "size": int(uploaded_file["size"]),
        "sha256": checksum,
        "local_verification": local_verification,
        "already_exists": False,
        "cloud_retention": retention_result,
    }


# --------------------------------------------------
# GOOGLE DRIVE ENCRYPTED DOWNLOAD
# --------------------------------------------------

def download_backup(
    file_id: str,
    destination: Path,
) -> dict:
    """
    Download and authenticate an encrypted Google Drive backup.

    destination can be:
    1. An existing directory. The cloud filename is used automatically.
    2. A complete timestamped .sql.enc filename matching the cloud file.

    The final encrypted destination is published only after:
    1. Cloud metadata validation.
    2. File size validation.
    3. SHA-256 validation.
    4. AES-GCM authentication.
    5. Decrypted SQL structure validation.

    The downloaded backup remains encrypted at rest.
    """

    if (
        not isinstance(file_id, str)
        or not file_id.strip()
    ):
        raise ValueError(
            "A Google Drive file ID is required."
        )

    destination = Path(destination).resolve()

    # Remember whether the caller supplied an existing directory.
    destination_is_directory = destination.is_dir()

    # If it is not a directory, require a valid timestamped filename.
    if not destination_is_directory:

        if not BACKUP_FILENAME_PATTERN.fullmatch(destination.name):
            raise ValueError(
                "Download destination must be a valid timestamped "
                ".sql.enc filename or an existing directory."
            )

    service = legacy_drive.authenticate_google_drive()

    metadata = legacy_drive.execute_with_retry(
        service.files().get(
            fileId=file_id,
            fields="id,name,size,description,mimeType",
        ),
        operation_name="Retrieve encrypted backup metadata",
    )

    if metadata.get("mimeType") == (
        "application/vnd.google-apps.folder"
    ):
        raise ValueError(
            "The supplied file ID refers to a folder."
        )

    cloud_file_name = metadata.get("name", "")

    if not BACKUP_FILENAME_PATTERN.fullmatch(cloud_file_name):
        raise ValueError(
            "The supplied Google Drive file is not a valid "
            "timestamped encrypted backup."
        )

    # If destination is a directory, append the exact cloud filename.
    if destination_is_directory:

        destination = destination / cloud_file_name

    # If destination is a filename, it must match the cloud filename.
    elif destination.name != cloud_file_name:

        raise ValueError(
            "Download destination filename must match the "
            "Google Drive backup filename."
        )

    if destination.exists():
        raise FileExistsError(
            f"Destination already exists: {destination}"
        )

    expected_size = int(
        metadata.get("size", -1)
    )

    if expected_size <= 0:
        raise RuntimeError(
            "Cloud backup metadata contains an invalid file size."
        )

    description = metadata.get(
        "description",
        "",
    )

    checksum_match = re.search(
        r"(?:^|\s)SHA256:([0-9a-fA-F]{64})(?:$|\s)",
        description,
    )

    if not checksum_match:
        raise RuntimeError(
            "Backup SHA-256 metadata is missing or invalid."
        )

    expected_checksum = checksum_match.group(1).lower()

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # The validator requires the temporary file's basename to match
    # BACKUP_FILENAME_PATTERN. A private temporary directory allows
    # us to retain the exact cloud filename without a naming conflict.
    with tempfile.TemporaryDirectory(
        prefix="encrypted_drive_download_",
        dir=destination.parent,
    ) as temporary_directory:

        temporary_path = (
            Path(temporary_directory) / destination.name
        )

        try:

            request = service.files().get_media(
                fileId=file_id
            )

            with temporary_path.open("xb") as output_file:

                downloader = MediaIoBaseDownload(
                    output_file,
                    request,
                )

                done = False

                while not done:
                    _, done = downloader.next_chunk()

            actual_size = temporary_path.stat().st_size

            if actual_size != expected_size:
                raise RuntimeError(
                    "Downloaded encrypted backup size mismatch."
                )

            actual_checksum = legacy_drive.calculate_sha256(
                temporary_path
            )

            if actual_checksum != expected_checksum:
                raise RuntimeError(
                    "Downloaded encrypted backup SHA-256 mismatch."
                )

            # Verify the encrypted artifact and its decrypted SQL.
            # The temporary filename satisfies the strict pattern.
            verification = validate_encrypted_backup(
                temporary_path
            )

            # Check again immediately before publishing.
            if destination.exists():
                raise FileExistsError(
                    f"Destination already exists: {destination}"
                )

            temporary_path.rename(destination)

            logger.info(
                "Encrypted cloud backup downloaded and authenticated: %s",
                cloud_file_name,
            )

            return {
                "file_name": cloud_file_name,
                "destination": str(destination),
                "size": actual_size,
                "sha256": actual_checksum,
                "verification": verification,
                "verified": True,
            }

        except Exception:

            logger.exception(
                "Encrypted Google Drive download or verification failed."
            )

            raise
