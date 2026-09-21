"""Authentication & Password Hashing Service (Argon2id + JWT Sessions).

Strictly enforces:
- No social login
- Argon2id password hashing via passlib
- Signed session tokens stored in HttpOnly cookies
- Magic link password reset tokens
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Configure Argon2id password hashing
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",  # Argon2id variant
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
)


class AuthError(Exception):
    """Base exception for authentication failures."""
    pass


class InvalidCredentialsError(AuthError):
    pass


class TokenExpiredError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


def hash_password(password: str) -> str:
    """Hashes plain password using Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against Argon2id hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT session token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and verifies a JWT session token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Session token has expired.") from exc
    except JWTError as exc:
        raise InvalidTokenError("Invalid session token.") from exc


def create_magic_link_token(email: str) -> str:
    """Generates a short-lived token (15 mins) for passwordless / recovery login."""
    return create_access_token(
        data={"sub": email, "type": "magic_link"},
        expires_delta=timedelta(minutes=15),
    )


def verify_magic_link_token(token: str) -> str:
    """Verifies a magic link token and returns the user email."""
    payload = decode_access_token(token)
    if payload.get("type") != "magic_link" or "sub" not in payload:
        raise InvalidTokenError("Invalid magic link token type.")
    return payload["sub"]
