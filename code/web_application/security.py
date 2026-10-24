"""HW7 authentication: bcrypt password hashing, JWT bearer tokens and role checks.

The HW4 server-side session (cookie) mechanism is kept only as history at the
hw4 git tag; every HW7 route uses JWT bearer authentication only.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import ROLES, User

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "s3209"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))

# auto_error=False: HTTPBearer would answer a missing header with 403; the
# contract for HW7 is 401 for a missing/invalid token, so we raise it ourselves.
bearer_scheme = HTTPBearer(auto_error=False)

# Used when the username does not exist, so a failed login costs the same bcrypt time.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt()).decode()


def _secret() -> str:
    """Return the JWT signing secret from .env (fails fast if it is missing or short)."""
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be set in .env (at least 32 characters)")
    return secret


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of the password (plain text is never stored)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Return True when the password matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), (password_hash or _DUMMY_HASH).encode())
    except ValueError:  # malformed hash in the table -> treat as a failed login
        return False


def create_access_token(user: User, minutes: int | None = None) -> str:
    """Return a signed JWT for the user (sub=username, role, iat, exp, iss)."""
    now = datetime.now(UTC)
    lifetime = ACCESS_TOKEN_MINUTES if minutes is None else minutes
    payload = {"sub": user.username, "uid": user.id, "role": user.role,
               "iss": JWT_ISSUER, "iat": now, "exp": now + timedelta(minutes=lifetime)}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def unauthorized(detail: str) -> HTTPException:
    """Return a 401 error that tells the client to use bearer authentication."""
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


def decode_token(token: str) -> dict:
    """Return the verified JWT claims, or raise 401 for an expired or invalid token."""
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER,
                          options={"require": ["sub", "exp", "iat", "iss"]})
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise unauthorized("Invalid token") from exc


def require_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
                 db: Session = Depends(get_db)) -> User:
    """Return the user named in a valid bearer token, or raise 401."""
    if creds is None or not creds.credentials:
        raise unauthorized("Not authenticated: missing bearer token")
    claims = decode_token(creds.credentials)
    user = db.query(User).filter(User.username == claims["sub"]).first()
    if user is None:
        raise unauthorized("Invalid token: user no longer exists")
    return user


def require_roles(*allowed: str) -> Callable[..., User]:
    """Return a dependency that allows only the given roles (others get 403)."""
    unknown = set(allowed) - set(ROLES)
    if not allowed or unknown:
        raise ValueError(f"require_roles needs roles from {ROLES}, got {allowed}")

    def checker(user: User = Depends(require_user)) -> User:
        # The role is read from MySQL, not trusted from the token, so a role
        # change takes effect immediately.
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{user.role}' cannot do this "
                       f"(requires {' or '.join(allowed)})")
        return user

    return checker


ANY_ROLE = require_user
WRITE_ROLES = require_roles("writer", "moderator")
MODERATOR_ONLY = require_roles("moderator")
