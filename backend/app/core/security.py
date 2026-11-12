from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
import jwt

from ..config import get_settings

_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    email: str,
    expires_minutes: int | None = None,
) -> tuple[str, str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    ttl = expires_minutes if expires_minutes is not None else settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    expires_at = now + timedelta(minutes=ttl)
    jti = uuid.uuid4().hex

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "email": email,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.CREDENTIALS_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_secret(plaintext_secret: str) -> str:
    """Encrypt API keys / OAuth tokens so plaintext credentials are NEVER persisted."""
    return _get_fernet().encrypt(plaintext_secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_secret: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored tool credential") from exc


def mask_secret(plaintext_secret: str, tenant_id: uuid.UUID, tool_slug: str) -> str:
    tail = plaintext_secret[-4:] if len(plaintext_secret) >= 4 else "****"
    return f"vault://{tenant_id}/{tool_slug}/••••••••{tail}"
