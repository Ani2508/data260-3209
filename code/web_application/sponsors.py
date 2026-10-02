"""HW5 Part 1: CRUD for the related entity (Sponsor) + relationship query."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Sponsor, Trial
from schemas import Page, SponsorIn, SponsorOut, TrialOut
from security import require_user
from trials import trial_out

router = APIRouter(prefix="/api/sponsors", tags=["sponsors"],
                   dependencies=[Depends(require_user)])


def get_sponsor_or_404(db: Session, sponsor_id: int) -> Sponsor:
    sponsor = db.get(Sponsor, sponsor_id)
    if not sponsor:
        raise HTTPException(status_code=404, detail=f"Sponsor {sponsor_id} not found")
    return sponsor


def ensure_email_free(db: Session, email: str, exclude_id: int | None = None):
    q = db.query(Sponsor).filter(Sponsor.contact_email == email)
    if exclude_id is not None:
        q = q.filter(Sponsor.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=409,
                            detail=f"contact_email '{email}' is already used by another sponsor")


@router.post("", status_code=201, response_model=SponsorOut)
def create_sponsor(body: SponsorIn, db: Session = Depends(get_db)):
    ensure_email_free(db, body.contact_email)
    sponsor = Sponsor(**body.model_dump())
    db.add(sponsor)
    db.commit()
    db.refresh(sponsor)
    return sponsor


@router.get("", response_model=Page[SponsorOut])
def list_sponsors(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                  db: Session = Depends(get_db)):
    total = db.query(func.count(Sponsor.id)).scalar()
    rows = (db.query(Sponsor).order_by(Sponsor.id)
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/{sponsor_id}", response_model=SponsorOut)
def get_sponsor(sponsor_id: int, db: Session = Depends(get_db)):
    return get_sponsor_or_404(db, sponsor_id)


@router.put("/{sponsor_id}", response_model=SponsorOut)
def update_sponsor(sponsor_id: int, body: SponsorIn, db: Session = Depends(get_db)):
    sponsor = get_sponsor_or_404(db, sponsor_id)
    ensure_email_free(db, body.contact_email, exclude_id=sponsor_id)
    for key, value in body.model_dump().items():
        setattr(sponsor, key, value)
    db.commit()
    db.refresh(sponsor)
    return sponsor


@router.delete("/{sponsor_id}")
def delete_sponsor(sponsor_id: int, db: Session = Depends(get_db)):
    sponsor = get_sponsor_or_404(db, sponsor_id)
    linked = db.query(func.count(Trial.id)).filter(Trial.sponsor_id == sponsor_id).scalar()
    if linked:
        raise HTTPException(
            status_code=409,
            detail=f"Sponsor {sponsor_id} still has {linked} trial(s); "
                   "delete or reassign them before deleting the sponsor")
    db.delete(sponsor)
    db.commit()
    return {"message": "Sponsor deleted", "id": sponsor_id}


# Relationship query: all trials run by one sponsor
@router.get("/{sponsor_id}/trials", response_model=list[TrialOut])
def trials_for_sponsor(sponsor_id: int, db: Session = Depends(get_db)):
    get_sponsor_or_404(db, sponsor_id)
    rows = (db.query(Trial).options(joinedload(Trial.sponsor))
            .filter(Trial.sponsor_id == sponsor_id).order_by(Trial.id).all())
    return [trial_out(t) for t in rows]
