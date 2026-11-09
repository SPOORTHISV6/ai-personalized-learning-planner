
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CREDENTIALS_FILE = (
    PROJECT_ROOT / "secrets" / "google_drive_credentials.json"
)

TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive.file"
]

DRIVE_FOLDER_NAME = "AI_Learning_Planner_Backups"

CLOUD_RETENTION_DATES = 7

logger = logging.getLogger(__name__)


# ============================================================
# OAUTH TOKEN MANAGEMENT
# ============================================================

def save_credentials(credentials):
    """
    Save OAuth credentials safely using a temporary file.
    """

    TOKEN_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_token = TOKEN_FILE.with_name(
        TOKEN_FILE.name + ".tmp"
    )

    try:
        temporary_token.write_text(
            credentials.to_json(),
            encoding="utf-8"
        )

        temporary_token.replace(TOKEN_FILE)

    finally:
        temporary_token.unlink(missing_ok=True)


# ============================================================
# GOOGLE DRIVE AUTHENTICATION
# ============================================================

def authenticate_google_drive():
    """
    Authenticate using OAuth installed-app flow.

    Features:
    - Reuses existing OAuth credentials.
    - Refreshes expired access tokens.
    - Persists refreshed credentials.
    - Starts browser authentication if refresh is unavailable.
    - Handles expired or revoked refresh tokens.
    """

    credentials = None

    # --------------------------------------------------------
    # 1. Load existing credentials
    # --------------------------------------------------------

    if TOKEN_FILE.exists():

        try:

            credentials = Credentials.from_authorized_user_file(
                str(TOKEN_FILE),
                SCOPES
            )

        except (OSError, ValueError):

            logger.warning(
                "Existing OAuth token could not be loaded. "
                "Fresh authentication will be required.",
                exc_info=True
            )

            credentials = None

    # --------------------------------------------------------
    # 2. Refresh expired access token
    # --------------------------------------------------------

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):

        try:

            credentials.refresh(Request())

            save_credentials(credentials)

            logger.info(
                "Google Drive OAuth token refreshed successfully."
            )

        except RefreshError:

            logger.warning(
                "Google Drive refresh token is invalid or expired. "
                "Fresh OAuth authentication is required.",
                exc_info=True
            )

            credentials = None

    # --------------------------------------------------------
    # 3. Start fresh authentication if necessary
    # --------------------------------------------------------

    if not credentials or not credentials.valid:

        if not CREDENTIALS_FILE.exists():

            raise FileNotFoundError(
                f"OAuth credentials not found: {CREDENTIALS_FILE}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            SCOPES
        )

        credentials = flow.run_local_server(
            host="127.0.0.1",
            bind_addr="127.0.0.1",
            port=0,
            open_browser=True,
            access_type="offline",
            prompt="consent"
        )

        save_credentials(credentials)

        logger.info(
            "Fresh Google Drive authentication completed."
        )

    # --------------------------------------------------------
    # 4. Build Google Drive API service
    # --------------------------------------------------------

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


# ============================================================
# SHA-256 CHECKSUM CALCULATION
# ============================================================

def calculate_sha256(file_path: Path) -> str:
    """
    Calculate SHA-256 checksum without loading
    the entire file into memory.
    """

    file_path = Path(file_path)

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:

        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# SQL BACKUP VALIDATION
# ============================================================

def validate_sql_backup(file_path: Path):
    """
    Validate SQL backup using the existing backup manager.
    """

    from app.database.backup_manager import verify_backup

    verification = verify_backup(Path(file_path))

    if verification is False:

        raise RuntimeError(
            f"SQL backup validation failed: {file_path}"
        )

    if (
        isinstance(verification, dict)
        and verification.get("valid") is False
    ):

        raise RuntimeError(
            f"SQL backup validation failed: {file_path}"
        )

    return verification


# ============================================================
# GOOGLE DRIVE BACKUP FOLDER
# ============================================================

def get_or_create_backup_folder(service) -> str:
    """
    Find or create the application backup folder.

    Handles paginated Google Drive search results.
    """

    query = (
        "mimeType='application/vnd.google-apps.folder' "
        f"and name='{DRIVE_FOLDER_NAME}' "
        "and trashed=false"
    )

    folders = []

    page_token = None

    while True:

        response = service.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name)",
            pageSize=100,
            pageToken=page_token
        ).execute()

        folders.extend(
            response.get("files", [])
        )

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    if folders:

        if len(folders) > 1:

            logger.warning(
                "Multiple Google Drive backup folders found. "
                "Using the first matching folder."
            )

        return folders[0]["id"]

    folder_metadata = {
        "name": DRIVE_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder"
    }

    folder = service.files().create(
        body=folder_metadata,
        fields="id"
    ).execute()

    logger.info(
        "Created Google Drive backup folder: %s",
        DRIVE_FOLDER_NAME
    )

    return folder["id"]


# ============================================================
# DUPLICATE BACKUP DETECTION
# ============================================================

def find_existing_backup(
    service,
    folder_id: str,
    file_name: str
):
    """
    Find an existing backup with the same name
    inside the application backup folder.

    Raises an error if multiple matching backups exist.
    """

    escaped_name = (
        file_name
        .replace("\\", "\\\\")
        .replace("'", "\\'")
    )

    query = (
        f"name='{escaped_name}' "
        f"and '{folder_id}' in parents "
        "and trashed=false"
    )

    matching_files = []

    page_token = None

    while True:

        response = service.files().list(
            q=query,
            spaces="drive",
            fields=(
                "nextPageToken, "
                "files(id, name, size, description, parents)"
            ),
            pageSize=100,
            pageToken=page_token
        ).execute()

        matching_files.extend(
            response.get("files", [])
        )

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    if not matching_files:
        return None

    if len(matching_files) > 1:

        raise RuntimeError(
            "Multiple Google Drive backups found "
            f"with name: {file_name}"
        )

    return matching_files[0]


# ============================================================
# CLOUD BACKUP RETENTION
# ============================================================

def apply_cloud_retention(
    service,
    folder_id: str,
    keep_dates: int = CLOUD_RETENTION_DATES
) -> dict:
    """
    Retain backups from the latest distinct dates.

    Only files matching:

    ai_learning_planner_YYYYMMDD_HHMMSS.sql

    are considered.

    Complete date and time validation is performed.

    Older matching backups are moved to Google Drive trash.
    They are not permanently deleted.
    """

    if (
        not isinstance(keep_dates, int)
        or isinstance(keep_dates, bool)
        or keep_dates < 1
    ):

        raise ValueError(
            "keep_dates must be an integer of at least 1."
        )

    backup_pattern = re.compile(
        r"^ai_learning_planner_(\d{8})_(\d{6})\.sql$"
    )

    backups = []

    page_token = None

    # --------------------------------------------------------
    # 1. Retrieve all files using pagination
    # --------------------------------------------------------

    while True:

        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            fields=(
                "nextPageToken, "
                "files(id, name, size, description)"
            ),
            pageSize=100,
            pageToken=page_token
        ).execute()

        for cloud_file in response.get("files", []):

            file_name = cloud_file.get("name", "")

            match = backup_pattern.fullmatch(file_name)

            if not match:
                continue

            date_string = match.group(1)
            time_string = match.group(2)

            try:

                backup_datetime = datetime.strptime(
                    f"{date_string}_{time_string}",
                    "%Y%m%d_%H%M%S"
                )

            except ValueError:

                logger.warning(
                    "Ignoring backup with invalid timestamp: %s",
                    file_name
                )

                continue

            backups.append({
                "id": cloud_file["id"],
                "name": file_name,
                "date": backup_datetime.date()
            })

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    # --------------------------------------------------------
    # 2. Identify latest distinct backup dates
    # --------------------------------------------------------

    distinct_dates = sorted(
        {
            backup["date"]
            for backup in backups
        },
        reverse=True
    )

    retained_dates = set(
        distinct_dates[:keep_dates]
    )

    # --------------------------------------------------------
    # 3. Move expired backups to trash
    # --------------------------------------------------------

    trashed_count = 0
    retained_count = 0

    for backup in backups:

        if backup["date"] in retained_dates:

            retained_count += 1

            continue

        service.files().update(
            fileId=backup["id"],
            body={"trashed": True},
            fields="id,name,trashed"
        ).execute()

        logger.info(
            "Moved expired cloud backup to trash: %s",
            backup["name"]
        )

        trashed_count += 1

    # --------------------------------------------------------
    # 4. Return retention result
    # --------------------------------------------------------

    result = {
        "total_backups": len(backups),
        "retained_dates": len(retained_dates),
        "retained_files": retained_count,
        "trashed_files": trashed_count
    }

    logger.info(
        "Cloud retention completed: %s",
        result
    )

    return result


# ============================================================
# GOOGLE DRIVE BACKUP UPLOAD
# ============================================================

def upload_backup(file_path: Path) -> dict:
    """
    Upload a verified SQL backup to Google Drive.

    Features:
    - Local file validation.
    - SQL backup validation.
    - SHA-256 calculation.
    - Duplicate prevention.
    - Upload verification.
    - Cleanup after failed upload verification.
    - Cloud retention.
    """

    file_path = Path(file_path).resolve()

    # --------------------------------------------------------
    # 1. Validate local backup file
    # --------------------------------------------------------

    if not file_path.is_file():

        raise FileNotFoundError(
            f"Backup file not found: {file_path}"
        )

    if file_path.suffix.lower() != ".sql":

        raise ValueError(
            "Only SQL backup files can be uploaded."
        )

    file_size = file_path.stat().st_size

    if file_size == 0:

        raise ValueError(
            "Cannot upload an empty backup."
        )

    # --------------------------------------------------------
    # 2. Validate SQL backup contents
    # --------------------------------------------------------

    verification = validate_sql_backup(file_path)

    # --------------------------------------------------------
    # 3. Calculate SHA-256 checksum
    # --------------------------------------------------------

    checksum = calculate_sha256(file_path)

    # --------------------------------------------------------
    # 4. Authenticate and locate backup folder
    # --------------------------------------------------------

    service = authenticate_google_drive()

    folder_id = get_or_create_backup_folder(service)

    # --------------------------------------------------------
    # 5. Check for duplicate backup
    # --------------------------------------------------------

    existing_file = find_existing_backup(
        service,
        folder_id,
        file_path.name
    )

    if existing_file:

        existing_size = int(
            existing_file.get("size", -1)
        )

        existing_description = existing_file.get(
            "description",
            ""
        )

        expected_description = f"SHA256:{checksum}"

        if (
            existing_size == file_size
            and expected_description in existing_description
        ):

            logger.info(
                "Identical cloud backup already exists: %s",
                file_path.name
            )

            retention_result = apply_cloud_retention(
                service,
                folder_id,
                keep_dates=CLOUD_RETENTION_DATES
            )

            return {
                "file_id": existing_file["id"],
                "file_name": existing_file["name"],
                "size": existing_size,
                "sha256": checksum,
                "local_verification": verification,
                "already_exists": True,
                "cloud_retention": retention_result
            }

        raise RuntimeError(
            "A Google Drive backup with the same filename "
            "already exists, but its size or checksum differs. "
            "The existing backup was not modified."
        )

    # --------------------------------------------------------
    # 6. Prepare upload metadata
    # --------------------------------------------------------

    metadata = {
        "name": file_path.name,
        "parents": [folder_id],
        "description": f"SHA256:{checksum}"
    }

    media = MediaFileUpload(
        str(file_path),
        mimetype="application/sql",
        resumable=True
    )

    uploaded_file = None

    # --------------------------------------------------------
    # 7. Upload and verify
    # --------------------------------------------------------

    try:

        uploaded_file = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name,size,description,parents"
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
                "Uploaded file size does not match "
                "the local backup."
            )

        uploaded_description = uploaded_file.get(
            "description",
            ""
        )

        if f"SHA256:{checksum}" not in uploaded_description:

            raise RuntimeError(
                "Uploaded checksum metadata does not match."
            )

    except Exception:

        if uploaded_file and uploaded_file.get("id"):

            try:

                service.files().update(
                    fileId=uploaded_file["id"],
                    body={"trashed": True},
                    fields="id,name,trashed"
                ).execute()

                logger.warning(
                    "Unverified uploaded backup moved to trash: %s",
                    file_path.name
                )

            except Exception:

                logger.exception(
                    "Could not clean up unverified uploaded backup: %s",
                    file_path.name
                )

        logger.exception(
            "Google Drive upload verification failed: %s",
            file_path.name
        )

        raise

    logger.info(
        "Cloud backup uploaded and metadata-checked: %s",
        file_path.name
    )

    # --------------------------------------------------------
    # 8. Apply cloud retention
    # --------------------------------------------------------

    retention_result = apply_cloud_retention(
        service,
        folder_id,
        keep_dates=CLOUD_RETENTION_DATES
    )

    logger.info(
        "Cloud retention result: %s",
        retention_result
    )

    # --------------------------------------------------------
    # 9. Return complete backup result
    # --------------------------------------------------------

    return {
        "file_id": uploaded_file["id"],
        "file_name": uploaded_file["name"],
        "size": int(uploaded_file["size"]),
        "sha256": checksum,
        "local_verification": verification,
        "already_exists": False,
        "cloud_retention": retention_result
    }


# ============================================================
# DOWNLOAD BACKUP FROM GOOGLE DRIVE
# ============================================================

def download_backup(
    file_id: str,
    destination: Path
) -> dict:
    """
    Download a Google Drive backup.

    Validates:
    - File ID.
    - SQL file extension.
    - File size.
    - SHA-256 checksum.
    - SQL backup contents.

    The final destination is created only after validation.
    """

    if not file_id or not file_id.strip():

        raise ValueError(
            "A Google Drive file ID is required."
        )

    destination = Path(destination).resolve()

    if destination.suffix.lower() != ".sql":

        raise ValueError(
            "Download destination must end in .sql."
        )

    if destination.exists():

        raise FileExistsError(
            f"Destination already exists: {destination}"
        )

    service = authenticate_google_drive()

    # --------------------------------------------------------
    # 1. Retrieve cloud backup metadata
    # --------------------------------------------------------

    metadata = service.files().get(
        fileId=file_id,
        fields="id,name,size,description,mimeType"
    ).execute()

    if metadata.get("mimeType") == (
        "application/vnd.google-apps.folder"
    ):

        raise ValueError(
            "The supplied file ID refers to a folder."
        )

    cloud_file_name = metadata.get("name", "")

    if not cloud_file_name.lower().endswith(".sql"):

        raise ValueError(
            "The supplied Google Drive file is not an SQL backup."
        )

    expected_size = int(
        metadata["size"]
    )

    description = metadata.get(
        "description",
        ""
    )

    # --------------------------------------------------------
    # 2. Extract and validate SHA-256 metadata
    # --------------------------------------------------------

    checksum_match = re.search(
        r"(?:^|\s)SHA256:([0-9a-fA-F]{64})(?:$|\s)",
        description
    )

    if not checksum_match:

        raise RuntimeError(
            "Backup SHA-256 metadata is missing or invalid."
        )

    expected_checksum = checksum_match.group(1).lower()

    # --------------------------------------------------------
    # 3. Prepare destination and temporary file
    # --------------------------------------------------------

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_path = destination.with_name(
        f"{destination.name}.{uuid4().hex}.partial"
    )

    try:

        request = service.files().get_media(
            fileId=file_id
        )

        # ----------------------------------------------------
        # 4. Download into temporary file
        # ----------------------------------------------------

        with temporary_path.open("wb") as file:

            downloader = MediaIoBaseDownload(
                file,
                request
            )

            done = False

            while not done:

                _, done = downloader.next_chunk()

        # ----------------------------------------------------
        # 5. Verify downloaded file size
        # ----------------------------------------------------

        actual_size = temporary_path.stat().st_size

        if actual_size != expected_size:

            raise RuntimeError(
                "Downloaded backup size mismatch."
            )

        # ----------------------------------------------------
        # 6. Verify downloaded SHA-256 checksum
        # ----------------------------------------------------

        actual_checksum = calculate_sha256(
            temporary_path
        )

        if actual_checksum != expected_checksum:

            raise RuntimeError(
                "Downloaded backup SHA-256 checksum mismatch."
            )

        # ----------------------------------------------------
        # 7. Validate downloaded SQL contents
        # ----------------------------------------------------

        verification = validate_sql_backup(
            temporary_path
        )

        # ----------------------------------------------------
        # 8. Move verified backup to final destination
        # ----------------------------------------------------

        if destination.exists():

            raise FileExistsError(
                f"Destination already exists: {destination}"
            )

        temporary_path.replace(destination)

        logger.info(
            "Cloud backup downloaded and validated: %s",
            cloud_file_name
        )

        return {
            "file_name": cloud_file_name,
            "destination": str(destination),
            "size": actual_size,
            "sha256": actual_checksum,
            "local_verification": verification,
            "verified": True
        }

    except Exception:

        temporary_path.unlink(missing_ok=True)

        logger.exception(
            "Google Drive backup download or verification failed."
        )

        raise
