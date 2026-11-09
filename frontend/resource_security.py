from pathlib import Path, PureWindowsPath


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_resource_path(resource):
    """
    Resolve a resource only when it is an existing PDF
    inside the trusted data/documents directory.

    Reject:
    - Absolute paths
    - POSIX and Windows directory traversal
    - Symlink escapes
    - A documents directory symlink outside the project
    - Non-PDF files
    - Missing files
    - Null-byte paths
    - Invalid resource metadata
    """

    if not isinstance(resource, dict):
        return ""

    raw_path = (
        resource.get("content_path")
        or resource.get("file_path")
        or resource.get("path")
        or ""
    )

    if not isinstance(raw_path, str) or not raw_path.strip():
        return ""

    raw_path = raw_path.strip()

    # Reject null bytes and control characters.
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in raw_path
    ):
        return ""

    try:
        project_root = PROJECT_ROOT.resolve(strict=True)

        # Normalize Windows separators before checking traversal.
        normalized_path = raw_path.replace("\\", "/")

        relative_path = Path(normalized_path)
        windows_path = PureWindowsPath(raw_path)

        # Reject POSIX and Windows absolute paths.
        if relative_path.is_absolute() or windows_path.is_absolute():
            return ""

        # Reject Windows drive paths, including drive-relative paths.
        if windows_path.drive:
            return ""

        # Reject directory traversal in either path representation.
        if ".." in relative_path.parts:
            return ""

        if ".." in windows_path.parts:
            return ""

        # The trusted documents directory must itself resolve
        # inside the project root.
        trusted_directory = (
            project_root / "data" / "documents"
        ).resolve(strict=True)

        try:
            trusted_directory.relative_to(project_root)
        except ValueError:
            return ""

        if not trusted_directory.is_dir():
            return ""

        # Resolve the complete candidate path, including symlinks.
        candidate_path = (
            project_root / relative_path
        ).resolve(strict=True)

        # The candidate must remain inside the trusted directory.
        try:
            candidate_path.relative_to(trusted_directory)
        except ValueError:
            return ""

        # Only PDF files are allowed.
        if candidate_path.suffix.lower() != ".pdf":
            return ""

        # Require a real existing regular file.
        if not candidate_path.is_file():
            return ""

        return str(candidate_path)

    except (
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
    ):
        return ""