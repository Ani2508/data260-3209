import time
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "hw3pass"
SESSION_TIMEOUT_SECONDS = 300


def session_is_active(request: Request) -> bool:
    username = request.session.get("user")
    last_activity = request.session.get("last_activity")

    if not username or not last_activity:
        return False

    if time.time() - last_activity > SESSION_TIMEOUT_SECONDS:
        request.session.clear()
        return False

    request.session["last_activity"] = time.time()
    return True


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    username = request.session.get("user")

    if username and session_is_active(request):
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={"username": username},
        )

    request.session.clear()

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"username": None},
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"message": None},
    )


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username != DEMO_USERNAME or password != DEMO_PASSWORD:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"message": "Invalid username or password."},
            status_code=401,
        )

    request.session.clear()
    request.session["user"] = username
    request.session["last_activity"] = time.time()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not session_is_active(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"username": request.session["user"]},
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)