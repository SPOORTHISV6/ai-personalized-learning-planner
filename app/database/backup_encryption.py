import os
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


MAGIC_HEADER = b"AIPLBK01"
NONCE_SIZE = 12
KEY_SIZE = 32
TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024


def get_encryption_key() -> bytes:
    """Load and validate the 256-bit encryption key."""

    raw_key = os.getenv("BACKUP_ENCRYPTION_KEY", "").strip()

    if not raw_key:
        raise RuntimeError(
            "BACKUP_ENCRYPTION_KEY is not configured."
        )

    try:
        key = bytes.fromhex(raw_key)
    except ValueError:
        raise RuntimeError(
            "BACKUP_ENCRYPTION_KEY must contain hexadecimal characters."
        ) from None

    if len(key) != KEY_SIZE:
        raise RuntimeError(
            "BACKUP_ENCRYPTION_KEY must represent exactly 32 bytes."
        )

    return key


def _validate_key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) != KEY_SIZE:
        raise ValueError(
            "AES-256-GCM requires a 32-byte encryption key."
        )

    return key


def _prepare_paths(source: Path, destination: Path):
    source = Path(source).resolve()
    destination = Path(destination).resolve()

    if not source.is_file():
        raise FileNotFoundError(
            f"Source file does not exist: {source}"
        )

    if source == destination:
        raise ValueError(
            "Source and destination must be different files."
        )

    if destination.exists():
        raise FileExistsError(
            f"Destination already exists: {destination}"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    return source, destination


def _create_temporary_file(destination: Path):
    """Create a temporary file in the destination directory."""

    temporary_file = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f"{destination.name}.",
        suffix=".partial",
        dir=destination.parent,
        delete=False
    )

    return temporary_file, Path(temporary_file.name)


def _publish_file(temporary_path: Path, destination: Path):
    """Atomically publish a completed file without intentional overwrite."""

    if destination.exists():
        raise FileExistsError(
            f"Destination already exists: {destination}"
        )

    # Path.rename uses the operating system's rename operation.
    # On Windows, it fails if the destination already exists.
    temporary_path.rename(destination)


def encrypt_file(
    source: Path,
    destination: Path,
    key: bytes | None = None
) -> dict:
    """
    Stream-encrypt a file using AES-256-GCM.

    File format:
        8-byte magic header
        12-byte random nonce
        ciphertext
        16-byte authentication tag

    The original source is never modified or deleted.
    """

    source, destination = _prepare_paths(
        source,
        destination
    )

    encryption_key = _validate_key(
        key if key is not None else get_encryption_key()
    )

    original_size = source.stat().st_size

    if original_size == 0:
        raise ValueError(
            "Cannot encrypt an empty backup."
        )

    nonce = os.urandom(NONCE_SIZE)

    encryptor = Cipher(
        algorithms.AES(encryption_key),
        modes.GCM(nonce)
    ).encryptor()

    encryptor.authenticate_additional_data(
        MAGIC_HEADER
    )

    temporary_path = None

    try:
        temporary_file, temporary_path = (
            _create_temporary_file(destination)
        )

        with temporary_file as output_file:
            output_file.write(MAGIC_HEADER)
            output_file.write(nonce)

            with source.open("rb") as input_file:
                while True:
                    chunk = input_file.read(CHUNK_SIZE)

                    if not chunk:
                        break

                    encrypted_chunk = encryptor.update(chunk)

                    if encrypted_chunk:
                        output_file.write(encrypted_chunk)

            final_chunk = encryptor.finalize()

            if final_chunk:
                output_file.write(final_chunk)

            output_file.write(encryptor.tag)

            output_file.flush()
            os.fsync(output_file.fileno())

        _publish_file(
            temporary_path,
            destination
        )

        temporary_path = None

        encrypted_size = destination.stat().st_size

        return {
            "source": str(source),
            "destination": str(destination),
            "original_size": original_size,
            "encrypted_size": encrypted_size,
            "algorithm": "AES-256-GCM",
            "authenticated": True
        }

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def decrypt_file(
    source: Path,
    destination: Path,
    key: bytes | None = None
) -> dict:
    """
    Stream-decrypt and authenticate an AES-256-GCM encrypted file.

    Plaintext remains in a temporary file until GCM authentication
    succeeds. An invalid tag never produces a published destination.
    """

    source, destination = _prepare_paths(
        source,
        destination
    )

    decryption_key = _validate_key(
        key if key is not None else get_encryption_key()
    )

    encrypted_size = source.stat().st_size

    minimum_size = (
        len(MAGIC_HEADER)
        + NONCE_SIZE
        + TAG_SIZE
        + 1
    )

    if encrypted_size < minimum_size:
        raise RuntimeError(
            "Encrypted backup is incomplete or invalid."
        )

    temporary_path = None

    try:
        with source.open("rb") as input_file:

            header = input_file.read(len(MAGIC_HEADER))

            if header != MAGIC_HEADER:
                raise RuntimeError(
                    "Encrypted backup format is not recognized."
                )

            nonce = input_file.read(NONCE_SIZE)

            if len(nonce) != NONCE_SIZE:
                raise RuntimeError(
                    "Encrypted backup nonce is incomplete."
                )

            # The authentication tag is stored at the end.
            input_file.seek(-TAG_SIZE, os.SEEK_END)
            tag = input_file.read(TAG_SIZE)

            if len(tag) != TAG_SIZE:
                raise RuntimeError(
                    "Encrypted backup authentication tag is incomplete."
                )

            ciphertext_start = (
                len(MAGIC_HEADER) + NONCE_SIZE
            )

            ciphertext_size = (
                encrypted_size
                - ciphertext_start
                - TAG_SIZE
            )

            if ciphertext_size <= 0:
                raise RuntimeError(
                    "Encrypted backup contains no ciphertext."
                )

            decryptor = Cipher(
                algorithms.AES(decryption_key),
                modes.GCM(nonce, tag)
            ).decryptor()

            decryptor.authenticate_additional_data(
                MAGIC_HEADER
            )

            temporary_file, temporary_path = (
                _create_temporary_file(destination)
            )

            with temporary_file as output_file:
                input_file.seek(ciphertext_start)

                remaining = ciphertext_size

                while remaining > 0:
                    chunk = input_file.read(
                        min(CHUNK_SIZE, remaining)
                    )

                    if not chunk:
                        raise RuntimeError(
                            "Encrypted backup ended unexpectedly."
                        )

                    remaining -= len(chunk)

                    plaintext_chunk = decryptor.update(chunk)

                    if plaintext_chunk:
                        output_file.write(plaintext_chunk)

                # Critical: finalize verifies the authentication tag.
                # Nothing is published before this succeeds.
                final_chunk = decryptor.finalize()

                if final_chunk:
                    output_file.write(final_chunk)

                output_file.flush()
                os.fsync(output_file.fileno())

        _publish_file(
            temporary_path,
            destination
        )

        temporary_path = None

        decrypted_size = destination.stat().st_size

        return {
            "source": str(source),
            "destination": str(destination),
            "decrypted_size": decrypted_size,
            "algorithm": "AES-256-GCM",
            "authenticated": True
        }

    except InvalidTag:
        raise RuntimeError(
            "Backup authentication failed. "
            "The encryption key is incorrect or the file was modified."
        ) from None

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
