"""Primary entity (Trial) CRUD. HW5: nct_id, enrollment_slots, status, sponsor FK.

HW7 access control (JWT bearer): list/read = any authenticated role,
create/update = writer or moderator, delete = moderator only.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from database import get_db
from models import Sponsor, Trial, TrialNote
from schemas import Page, TrialIn, TrialOut
from security import MODERATOR_ONLY, WRITE_ROLES, require_user

router = APIRouter(prefix="/api/trials", tags=["trials"],
                   dependencies=[Depends(require_user)])


def trial_out(trial: Trial) -> dict:
    return {
        "id": trial.id, "trial_title": trial.trial_title, "nct_id": trial.nct_id,
        "enrollment_slots": trial.enrollment_slots, "status": trial.status,
        "sponsor_id": trial.sponsor_id,
        "sponsor_name": trial.sponsor.name if trial.sponsor else None,
        "created_at": trial.created_at, "updated_at": trial.updated_at,
    }


def get_or_404(db: Session, trial_id: int) -> Trial:
    trial = db.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return trial


def check_refs(db: Session, body: TrialIn, exclude_id: int | None = None):
    if not db.get(Sponsor, body.sponsor_id):
        raise HTTPException(status_code=422,
                            detail=f"sponsor_id {body.sponsor_id} does not exist")
    q = db.query(Trial).filter(Trial.nct_id == body.nct_id)
    if exclude_id is not None:
        q = q.filter(Trial.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=409,
                            detail=f"nct_id '{body.nct_id}' is already registered")


@router.get("", response_model=Page[TrialOut])
def list_trials(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db)):
    total = db.query(func.count(Trial.id)).scalar()
    rows = (db.query(Trial).options(joinedload(Trial.sponsor))
            .order_by(Trial.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [trial_out(t) for t in rows], "total": total,
            "page": page, "page_size": page_size}


@router.get("/search", response_model=list[TrialOut])
def search_trials(q: str = "", db: Session = Depends(get_db)):
    query = db.query(Trial).join(Sponsor).options(joinedload(Trial.sponsor))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Trial.trial_title.like(like), Sponsor.name.like(like),
                                 Trial.nct_id.like(like)))
    return [trial_out(t) for t in query.order_by(Trial.id.desc()).limit(100).all()]


@router.get("/{trial_id}", response_model=TrialOut)
def get_trial(trial_id: int, db: Session = Depends(get_db)):
    return trial_out(get_or_404(db, trial_id))


@router.post("", status_code=201, response_model=TrialOut,
             dependencies=[Depends(WRITE_ROLES)])
def create_trial(body: TrialIn, db: Session = Depends(get_db)):
    check_refs(db, body)
    trial = Trial(**body.model_dump())
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial_out(trial)


@router.put("/{trial_id}", response_model=TrialOut, dependencies=[Depends(WRITE_ROLES)])
def update_trial(trial_id: int, body: TrialIn, db: Session = Depends(get_db)):
    trial = get_or_404(db, trial_id)
    check_refs(db, body, exclude_id=trial_id)
    for key, value in body.model_dump().items():
        setattr(trial, key, value)
    db.commit()
    db.refresh(trial)
    return trial_out(trial)


@router.delete("/{trial_id}", dependencies=[Depends(MODERATOR_ONLY)])
def delete_trial(trial_id: int, db: Session = Depends(get_db)):
    trial = get_or_404(db, trial_id)
    db.delete(trial)
    db.commit()
    return {"message": "Trial deleted", "id": trial_id}


# ---------- HW4 N+1 demo endpoints (kept, now read sponsor via the FK) ----------
@router.get("/naive/list")
def list_trials_naive(page_size: int = 10, db: Session = Depends(get_db)):
    """Intentionally naive: 1 query for trials + 1 extra query PER trial for its notes."""
    trials = db.query(Trial).options(joinedload(Trial.sponsor)) \
        .order_by(Trial.id).limit(page_size).all()
    result = []
    for t in trials:
        notes = db.query(TrialNote).filter(TrialNote.trial_id == t.id).all()  # N+1
        result.append({"id": t.id, "trialTitle": t.trial_title,
                       "sponsor": t.sponsor.name, "notes": [n.note_text for n in notes]})
    return result


@router.get("/fixed/list")
def list_trials_fixed(page_size: int = 10, db: Session = Depends(get_db)):
    """Fixed: eager-loads notes and sponsor in a small, constant number of queries."""
    trials = (db.query(Trial)
              .options(selectinload(Trial.notes), joinedload(Trial.sponsor))
              .order_by(Trial.id).limit(page_size).all())
    return [{"id": t.id, "trialTitle": t.trial_title, "sponsor": t.sponsor.name,
             "notes": [n.note_text for n in t.notes]} for t in trials]
