import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserSession

COOKIE_NAME = "session_token"
SESSION_MINUTES = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session(db_session_basede26: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)  # random, holds no user data
    now = datetime.utcnow()
    db_session_basede26.add(UserSession(
        id=token, user_id=user.id, created_at=now,
        expires_at=now + timedelta(minutes=SESSION_MINUTES),
    ))
    db_session_basede26.commit()
    return token


def set_session_cookie(response, token: str):
    response.set_cookie(
        key=COOKIE_NAME, value=token, httponly=True, samesite="lax",
        secure=False,  # localhost is http; set True under https
        max_age=SESSION_MINUTES * 60, path="/",
    )


def get_user_from_request(request: Request, db_session_basede26: Session):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    session = db_session_basede26.get(UserSession, token)
    if not session:
        return None
    if session.expires_at < datetime.utcnow():
        db_session_basede26.delete(session)
        db_session_basede26.commit()
        return None
    return session.user


def delete_session(request: Request, db_session_basede26: Session):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session = db_session_basede26.get(UserSession, token)
        if session:
            db_session_basede26.delete(session)
            db_session_basede26.commit()


def require_user(request: Request,
                 db_session_basede26: Session = Depends(get_db)) -> User:
    user = get_user_from_request(request, db_session_basede26)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user