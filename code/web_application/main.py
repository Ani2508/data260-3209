import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError, WriteError
from sqlalchemy.exc import IntegrityError, OperationalError

import config
import models  # noqa: F401  (registers tables)
from auth import router as auth_router
from bikeshare_routes import router as bikeshare_router
from chat_routes import router as chat_router
from database import Base, engine, query_count
from doc_trials import router as doc_trials_router
from mongo_db import init_db
from sponsors import router as sponsors_router
from trials import router as trials_router

log = logging.getLogger("uvicorn.error")

try:
    Base.metadata.create_all(bind=engine)
except OperationalError as exc:      # MySQL down -> HW6 MongoDB routes still work
    log.warning("MySQL unavailable, relational routes disabled: %s", exc.orig)

app = FastAPI(title="Clinical Trial Listing API")

# Middleware: CORS (JSON request bodies are parsed by FastAPI/Pydantic)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

app.include_router(auth_router)                       # HW7: /auth/login, /auth/me
app.include_router(auth_router, prefix="/api",         # same JWT routes for the React app
                   include_in_schema=False)
app.include_router(trials_router)
app.include_router(sponsors_router)
app.include_router(doc_trials_router)
app.include_router(chat_router)
app.include_router(bikeshare_router)            # HW7 Part 4: /bikeshare UI


@app.on_event("startup")
def mongo_startup():
    try:
        init_db()
        log.info("MongoDB ready: %s/%s", config.MONGO_URI, config.MONGO_DB)
    except PyMongoError as exc:
        log.warning("MongoDB not reachable at startup: %s", exc)


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errors})


@app.exception_handler(WriteError)
def mongo_write_error(request: Request, exc: WriteError):
    # MongoDB $jsonSchema rejected the document (second line of defence)
    return JSONResponse(status_code=422, content={"detail": "Document failed MongoDB validation"})


@app.exception_handler(ServerSelectionTimeoutError)
def mongo_down(request: Request, exc: ServerSelectionTimeoutError):
    return JSONResponse(status_code=503, content={"detail": "MongoDB is not reachable"})


@app.exception_handler(Exception)
def server_error(request: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500,
                        content={"detail": f"Internal server error: {type(exc).__name__}"})


@app.exception_handler(IntegrityError)
def integrity_error(request: Request, exc: IntegrityError):
    # Safety net for DB constraint violations (unique / foreign key) -> 409
    return JSONResponse(status_code=409,
                        content={"detail": "Database constraint violated: " + str(exc.orig)})


@app.get("/api/debug/query-count")
def get_query_count():
    return {"queries": query_count["count"]}


@app.post("/api/debug/reset-query-count")
def reset_query_count():
    query_count["count"] = 0
    return {"queries": 0}


BASE_DIR = Path(__file__).resolve().parent
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")
