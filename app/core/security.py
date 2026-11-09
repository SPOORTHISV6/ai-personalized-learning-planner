from datetime import datetime, timedelta, timezone
from app.core.config import get_jwt_secret_key
import jwt
from pwdlib import PasswordHash


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hasher = PasswordHash.recommended()


def get_secret_key() -> str:
    """Read and validate the JWT signing key."""
    return get_jwt_secret_key()


def hash_password(password: str) -> str:
    """Return a secure password hash."""
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """Verify a password without storing the plain text."""
    return password_hasher.verify(
        plain_password,
        password_hash,
    )


def create_access_token(
    student_id: int,
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """Create a signed JWT for a student."""

    # Reject booleans, floats, strings, and invalid IDs.
    if (
        isinstance(student_id, bool)
        or not isinstance(student_id, int)
        or student_id <= 0
    ):
        raise ValueError(
            "student_id must be a positive integer."
        )

    # Expiration must be a positive integer.
    if (
        isinstance(expires_minutes, bool)
        or not isinstance(expires_minutes, int)
        or expires_minutes <= 0
    ):
        raise ValueError(
            "expires_minutes must be a positive integer."
        )

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(student_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }

    return jwt.encode(
        payload,
        get_secret_key(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    """Validate a JWT and return its student ID."""
    payload = jwt.decode(
        token,
        get_secret_key(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )

    subject = payload.get("sub")

    if not isinstance(subject, str) or not subject.isdigit():
        raise jwt.InvalidTokenError("Invalid token subject")

    student_id = int(subject)

    if student_id <= 0:
        raise jwt.InvalidTokenError("Invalid student ID")

    return student_id