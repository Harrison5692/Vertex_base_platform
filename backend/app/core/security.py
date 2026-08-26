"""
Password hashing (bcrypt, used directly — not via passlib, which
hasn't been updated since 2020 and breaks against current bcrypt
releases) and JWT issuance/verification.

This is what the `secret_key` config value is for — signing and
verifying login tokens.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

import bcrypt
import jwt

from app.core.config import settings

# bcrypt has a hard 72-byte input limit — truncate explicitly rather
# than let it silently (or in newer versions, loudly) fail on a long
# password.
_MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    pw_bytes = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    """Returns the subject (user email) if valid, None if expired/invalid."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def generate_reset_token() -> str:
    """The raw token — sent to the account, never stored as-is."""
    return secrets.token_urlsafe(32)


def hash_reset_token(raw_token: str) -> str:
    """What's actually stored in Account.reset_token_hash. A reset
    token is a bearer credential just like a password — hashing it
    means a leaked database doesn't hand out working reset links."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
