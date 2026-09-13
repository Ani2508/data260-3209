from typing import List
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


app = FastAPI(title="Clinical Trial Listing API")

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"


class TrialCreate(BaseModel):
    trialTitle: str
    sponsor: str
    email: str = ""
    content: str = ""
    status: str = "Recruiting"


class TrialUpdate(BaseModel):
    trialTitle: str
    sponsor: str


trials: List[dict] = []


@app.get("/")
def home():
    return FileResponse(INDEX_FILE)


@app.get("/api/trials")
def get_trials():
    return trials


@app.post("/api/trials")
def add_trial(trial: TrialCreate):
    new_id = max((item["id"] for item in trials), default=0) + 1

    new_trial = {
        "id": new_id,
        "trialTitle": trial.trialTitle,
        "sponsor": trial.sponsor,
        "email": trial.email,
        "content": trial.content,
        "status": trial.status,
    }

    trials.append(new_trial)

    return RedirectResponse(url="/", status_code=303)


@app.put("/api/trials/{trial_id}")
def update_trial(trial_id: int, trial: TrialUpdate):
    for item in trials:
        if item["id"] == trial_id:
            item["trialTitle"] = trial.trialTitle
            item["sponsor"] = trial.sponsor

            return RedirectResponse(url="/", status_code=303)

    raise HTTPException(
        status_code=404,
        detail="Trial record not found"
    )
@app.delete("/api/trials/highest")
def delete_highest_id_trial():
    if not trials:
        raise HTTPException(
            status_code=404,
            detail="No trial records available"
        )

    highest_id_trial = max(trials, key=lambda item: item["id"])
    trials.remove(highest_id_trial)

    return RedirectResponse(url="/", status_code=303)



@app.get("/api/trials/search")
def search_trials(q: str = ""):
    search_text = q.strip().lower()

    if not search_text:
        return trials

    matching_trials = [
        item
        for item in trials
        if search_text in item["trialTitle"].lower()
        or search_text in item["sponsor"].lower()
    ]

    return matching_trials
app.mount(
    "/",
    StaticFiles(directory=BASE_DIR, html=True),
    name="static"
)
