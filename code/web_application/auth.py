from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import (COOKIE_NAME, create_session, delete_session,
                      get_user_from_request, hash_password, require_user,
                      set_session_cookie, verify_password)

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------- JSON API (used by React + Postman) ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6)


class LoginIn(BaseModel):
    email: str
    password: str


def user_dict(user: User):
    return {"id": user.id, "name": user.name, "email": user.email}


@router.post("/api/auth/register", status_code=201)
def register(body: RegisterIn, db_session_basede26: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db_session_basede26.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(name=body.name.strip(), email=email,
                password_hash=hash_password(body.password))
    db_session_basede26.add(user)
    db_session_basede26.commit()
    db_session_basede26.refresh(user)
    return user_dict(user)


@router.post("/api/auth/login")
def api_login(body: LoginIn, response: Response,
              db_session_basede26: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db_session_basede26.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_session(db_session_basede26, user)
    set_session_cookie(response, token)  # token only in HTTP-only cookie
    return user_dict(user)


@router.post("/api/auth/logout")
def api_logout(request: Request, response: Response,
               db_session_basede26: Session = Depends(get_db)):
    delete_session(request, db_session_basede26)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"message": "Logged out"}


@router.get("/api/auth/me")
def me(user: User = Depends(require_user)):
    return user_dict(user)


# ---------- HW3 server-rendered pages (now use DB sessions) ----------
@router.get("/", response_class=HTMLResponse)
def home(request: Request, db_session_basede26: Session = Depends(get_db)):
    user = get_user_from_request(request, db_session_basede26)
    return templates.TemplateResponse(
        request=request, name="home.html",
        context={"username": user.name if user else None})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="login.html", context={"message": None})


@router.post("/login", response_class=HTMLResponse)
def login_form(request: Request, username: str = Form(...),
               password: str = Form(...),
               db_session_basede26: Session = Depends(get_db)):
    email = username.strip().lower()  # form field holds the email
    user = db_session_basede26.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request, name="login.html",
            context={"message": "Invalid email or password."}, status_code=401)
    token = create_session(db_session_basede26, user)
    response = RedirectResponse(url="/dashboard", status_code=303)
    set_session_cookie(response, token)
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db_session_basede26: Session = Depends(get_db)):
    user = get_user_from_request(request, db_session_basede26)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="dashboard.html", context={"username": user.name})


@router.get("/logout")
def logout(request: Request, db_session_basede26: Session = Depends(get_db)):
    delete_session(request, db_session_basede26)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response