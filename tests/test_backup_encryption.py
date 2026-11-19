import pytest

from app.database.backup_encryption import (
    encrypt_file,
    decrypt_file,
    get_encryption_key,
    CHUNK_SIZE,
)


TEST_KEY = bytes.fromhex("11" * 32)
WRONG_KEY = bytes.fromhex("22" * 32)


@pytest.fixture
def sample_backup(tmp_path):
    source = tmp_path / "sample.sql"

    content = (
        b"CREATE TABLE test_table (id INT);\n"
        b"INSERT INTO test_table VALUES (1);\n"
        b"-- Dump completed on 2026-11-14\n"
    )

    source.write_bytes(content)

    return source, content


def test_encrypt_backup_successfully(sample_backup, tmp_path):
    source, content = sample_backup
    encrypted = tmp_path / "sample.sql.enc"

    result = encrypt_file(source, encrypted, TEST_KEY)

    assert encrypted.exists()
    assert encrypted.read_bytes() != content
    assert result["algorithm"] == "AES-256-GCM"
    assert result["authenticated"] is True
    assert source.read_bytes() == content


def test_decrypt_backup_recovers_original(sample_backup, tmp_path):
    source, content = sample_backup
    encrypted = tmp_path / "sample.sql.enc"
    decrypted = tmp_path / "restored.sql"

    encrypt_file(source, encrypted, TEST_KEY)
    decrypt_file(encrypted, decrypted, TEST_KEY)

    assert decrypted.read_bytes() == content


def test_wrong_key_is_rejected(sample_backup, tmp_path):
    source, _ = sample_backup
    encrypted = tmp_path / "sample.sql.enc"
    decrypted = tmp_path / "restored.sql"

    encrypt_file(source, encrypted, TEST_KEY)

    with pytest.raises(RuntimeError, match="authentication failed"):
        decrypt_file(encrypted, decrypted, WRONG_KEY)

    assert not decrypted.exists()


def test_tampered_backup_is_rejected(sample_backup, tmp_path):
    source, _ = sample_backup
    encrypted = tmp_path / "sample.sql.enc"
    tampered = tmp_path / "tampered.sql.enc"
    decrypted = tmp_path / "restored.sql"

    encrypt_file(source, encrypted, TEST_KEY)

    data = bytearray(encrypted.read_bytes())
    data[-1] ^= 1
    tampered.write_bytes(data)

    with pytest.raises(RuntimeError, match="authentication failed"):
        decrypt_file(tampered, decrypted, TEST_KEY)

    assert not decrypted.exists()


def test_empty_backup_is_rejected(tmp_path):
    source = tmp_path / "empty.sql"
    destination = tmp_path / "empty.sql.enc"

    source.write_bytes(b"")

    with pytest.raises(ValueError, match="empty"):
        encrypt_file(source, destination, TEST_KEY)


def test_missing_encryption_key_is_rejected(monkeypatch):
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="not configured"):
        get_encryption_key()


def test_invalid_encryption_key_is_rejected(monkeypatch):
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "not-a-valid-key")

    with pytest.raises(RuntimeError, match="hexadecimal"):
        get_encryption_key()


def test_wrong_length_encryption_key_is_rejected(monkeypatch):
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "11" * 16)

    with pytest.raises(RuntimeError, match="32 bytes"):
        get_encryption_key()


def test_existing_destination_is_not_overwritten(
    sample_backup,
    tmp_path
):
    source, _ = sample_backup
    encrypted = tmp_path / "sample.sql.enc"

    encrypted.write_bytes(b"existing-content")

    with pytest.raises(FileExistsError):
        encrypt_file(source, encrypted, TEST_KEY)

    assert encrypted.read_bytes() == b"existing-content"


def test_encryption_rejects_same_source_and_destination(sample_backup):
    source, _ = sample_backup

    with pytest.raises(ValueError, match="different"):
        encrypt_file(source, source, TEST_KEY)


def test_incomplete_encrypted_file_is_rejected(tmp_path):
    encrypted = tmp_path / "broken.sql.enc"
    decrypted = tmp_path / "restored.sql"

    encrypted.write_bytes(b"AIPLBK01")

    with pytest.raises(RuntimeError, match="incomplete"):
        decrypt_file(encrypted, decrypted, TEST_KEY)

    assert not decrypted.exists()


def test_large_file_streaming_round_trip(tmp_path):
    source = tmp_path / "large.sql"
    encrypted = tmp_path / "large.sql.enc"
    decrypted = tmp_path / "restored.sql"

    content = (
        b"CREATE TABLE large_test (id INT);\n"
        + bytes(range(256)) * ((2 * CHUNK_SIZE) // 256 + 1)
    )

    source.write_bytes(content)

    encrypt_file(source, encrypted, TEST_KEY)
    decrypt_file(encrypted, decrypted, TEST_KEY)

    assert decrypted.read_bytes() == content
    assert encrypted.stat().st_size > 2 * CHUNK_SIZE


def test_repeated_encryption_uses_different_nonces(
    sample_backup,
    tmp_path
):
    source, _ = sample_backup

    first = tmp_path / "first.sql.enc"
    second = tmp_path / "second.sql.enc"

    encrypt_file(source, first, TEST_KEY)
    encrypt_file(source, second, TEST_KEY)

    first_data = first.read_bytes()
    second_data = second.read_bytes()

    assert first_data[:8] == second_data[:8] == b"AIPLBK01"
    assert first_data[8:20] != second_data[8:20]
    assert first_data != second_data


def test_tampered_large_file_leaves_no_published_plaintext(
    tmp_path
):
    source = tmp_path / "large.sql"
    encrypted = tmp_path / "large.sql.enc"
    tampered = tmp_path / "tampered.sql.enc"
    decrypted = tmp_path / "restored.sql"

    content = b"SQL-DATA-" * (CHUNK_SIZE // 9 + 100)
    source.write_bytes(content)

    encrypt_file(source, encrypted, TEST_KEY)

    data = bytearray(encrypted.read_bytes())
    data[CHUNK_SIZE + 20] ^= 1
    tampered.write_bytes(data)

    with pytest.raises(RuntimeError, match="authentication failed"):
        decrypt_file(tampered, decrypted, TEST_KEY)

    assert not decrypted.exists()
    assert not list(tmp_path.glob("restored.sql.*.partial"))


def test_large_file_is_not_modified_during_encryption(tmp_path):
    source = tmp_path / "large.sql"
    encrypted = tmp_path / "large.sql.enc"

    content = b"ORIGINAL-DATA-" * (CHUNK_SIZE // 14 + 100)
    source.write_bytes(content)

    encrypt_file(source, encrypted, TEST_KEY)

    assert source.read_bytes() == content
    assert encrypted.exists()
