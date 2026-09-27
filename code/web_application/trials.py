from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import Trial
from security import require_user
from models import Trial, TrialNote
from sqlalchemy.orm import selectinload


router = APIRouter(prefix="/api/trials", tags=["trials"],
                   dependencies=[Depends(require_user)])


class TrialIn(BaseModel):
    trialTitle: str = Field(min_length=1, max_length=255)
    sponsor: str = Field(min_length=1, max_length=255)


def to_dict(trial: Trial):
    return {"id": trial.id, "trialTitle": trial.trial_title,
            "sponsor": trial.sponsor}


def clean(body: TrialIn):
    title, sponsor = body.trialTitle.strip(), body.sponsor.strip()
    if not title or not sponsor:
        raise HTTPException(status_code=422, detail="Fields cannot be blank")
    return title, sponsor


def get_or_404(db_session_basede26: Session, trial_id: int) -> Trial:
    trial = db_session_basede26.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial record not found")
    return trial


@router.get("")
def list_trials(db_session_basede26: Session = Depends(get_db)):
    rows = db_session_basede26.query(Trial).order_by(Trial.id.desc()).all()
    return [to_dict(t) for t in rows]


@router.get("/search")
def search_trials(q: str = "", db_session_basede26: Session = Depends(get_db)):
    query = db_session_basede26.query(Trial)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(Trial.trial_title.like(like) | Trial.sponsor.like(like))
    return [to_dict(t) for t in query.order_by(Trial.id.desc()).all()]


@router.get("/{trial_id}")
def get_trial(trial_id: int, db_session_basede26: Session = Depends(get_db)):
    return to_dict(get_or_404(db_session_basede26, trial_id))


@router.post("", status_code=201)
def create_trial(body: TrialIn, db_session_basede26: Session = Depends(get_db)):
    title, sponsor = clean(body)
    trial = Trial(trial_title=title, sponsor=sponsor)
    db_session_basede26.add(trial)
    db_session_basede26.commit()
    db_session_basede26.refresh(trial)
    return to_dict(trial)


@router.put("/{trial_id}")
def update_trial(trial_id: int, body: TrialIn,
                 db_session_basede26: Session = Depends(get_db)):
    trial = get_or_404(db_session_basede26, trial_id)
    trial.trial_title, trial.sponsor = clean(body)
    db_session_basede26.commit()
    return to_dict(trial)


@router.delete("/{trial_id}")
def delete_trial(trial_id: int, db_session_basede26: Session = Depends(get_db)):
    trial = get_or_404(db_session_basede26, trial_id)
    db_session_basede26.delete(trial)
    db_session_basede26.commit()
    return {"message": "Trial deleted", "id": trial_id}

@router.get("/naive/list")
def list_trials_naive(page_size: int = 10, db_session_basede26: Session = Depends(get_db)):
    """Intentionally naive: 1 query for trials + 1 extra query PER trial for its notes."""
    trials = (
        db_session_basede26.query(Trial)
        .order_by(Trial.id)
        .limit(page_size)
        .all()
    )  # query #1

    result = []
    for t in trials:
        notes = (
            db_session_basede26.query(TrialNote)
            .filter(TrialNote.trial_id == t.id)
            .all()
        )  # 1 extra query per trial — this is the N+1 problem
        result.append({
            "id": t.id,
            "trialTitle": t.trial_title,
            "sponsor": t.sponsor,
            "notes": [n.note_text for n in notes],
        })
    return result

@router.get("/fixed/list")
def list_trials_fixed(page_size: int = 10, db_session_basede26: Session = Depends(get_db)):
    """Fixed: eager-loads notes with the trials in a small, constant number of queries."""
    trials = (
        db_session_basede26.query(Trial)
        .options(selectinload(Trial.notes))
        .order_by(Trial.id)
        .limit(page_size)
        .all()
    )  # query #1: trials, query #2: all their notes in one IN(...) query

    return [
        {
            "id": t.id,
            "trialTitle": t.trial_title,
            "sponsor": t.sponsor,
            "notes": [n.note_text for n in t.notes],
        }
        for t in trials
    ]
