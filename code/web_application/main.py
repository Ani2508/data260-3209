from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import models  # noqa: F401  (registers tables)
from auth import router as auth_router
from database import Base, engine, query_count
from trials import router as trials_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Clinical Trial Listing API")
app.include_router(auth_router)
app.include_router(trials_router)


@app.get("/api/debug/query-count")
def get_query_count():
    return {"queries": query_count["count"]}


@app.post("/api/debug/reset-query-count")
def reset_query_count():
    query_count["count"] = 0
    return {"queries": 0}


BASE_DIR = Path(__file__).resolve().parent
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")