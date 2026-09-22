"""JWT authentication and development user bootstrap."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import User


ALGORITHM = "HS256"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, iterations: int = 210_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64_encode(salt)}${_b64_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        salt = _b64_decode(salt_text)
        expected = _b64_decode(digest_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.access_token_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at, "iat": datetime.now(timezone.utc)}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), int(expires_delta.total_seconds())


def ensure_default_admin(db: Session) -> None:
    if db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first() is not None:
        return
    db.add(
        User(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
    )
    db.commit()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_error
    except jwt.PyJWTError as exc:
        raise credentials_error from exc
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency
