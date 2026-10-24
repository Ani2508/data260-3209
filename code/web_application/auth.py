"""HW7 auth routes: POST /auth/login (JWT), GET /auth/me, POST /auth/register.

The HW4 cookie/session login and the server-rendered login pages are kept only
as history at the hw4 tag; HW7 routes accept JWT bearer tokens only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import (
    ACCESS_TOKEN_MINUTES,
    create_access_token,
    hash_password,
    require_user,
    unauthorized,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100, examples=["s3209_writer"])
    password: str = Field(min_length=1, max_length=128)


class RegisterIn(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,50}$", examples=["new_reader"])
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    role: str


def user_dict(user: User) -> dict:
    """Return the public identity of a user (never the password hash)."""
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    """Return a JWT access token for valid credentials, otherwise 401."""
    user = db.query(User).filter(User.username == body.username.strip()).first()
    # verify_password always runs bcrypt, so unknown users and wrong passwords
    # take the same time and get the same message.
    password_ok = verify_password(body.password, user.password_hash if user else None)
    if user is None or not password_ok:
        raise unauthorized("Invalid username or password")
    return {"access_token": create_access_token(user), "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_MINUTES * 60,
            "username": user.username, "role": user.role}


@router.get("/me")
def me(user: User = Depends(require_user)) -> dict:
    """Return the authenticated user's id, username and role."""
    return user_dict(user)


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> dict:
    """Create a self-registered account; it is always given the reader role."""
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username already registered")
    user = User(username=body.username, password_hash=hash_password(body.password),
                role="reader")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_dict(user)
