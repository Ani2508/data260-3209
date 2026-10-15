"""Route handlers: CRUD for the MongoDB document view of clinical trials (HW6 Part 1)."""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, Response, status
from pymongo import ReturnDocument

from doc_schemas import DocTrialCreate, DocTrialOut, DocTrialUpdate
from mongo_db import get_db

router = APIRouter(prefix="/api/doc/trials", tags=["doc-trials (MongoDB)"])


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _oid(trial_id: str) -> ObjectId:
    try:
        return ObjectId(trial_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"'{trial_id}' is not a valid ObjectId")


def _out(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("", response_model=DocTrialOut, status_code=status.HTTP_201_CREATED)
def create_trial(body: DocTrialCreate):
    now = _now()
    doc = body.model_dump(mode="python")
    doc["status"], doc["phase"] = body.status.value, body.phase.value
    doc.update(created_at=now, updated_at=now)
    result = get_db().trials.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _out(doc)


@router.get("", response_model=list[DocTrialOut])
def list_trials(status_: str | None = Query(None, alias="status"),
                limit: int = Query(50, ge=1, le=200)):
    query = {"status": status_} if status_ else {}
    docs = get_db().trials.find(query).sort("start_date", 1).limit(limit)
    return [_out(d) for d in docs]


@router.get("/{trial_id}", response_model=DocTrialOut)
def get_trial(trial_id: str):
    doc = get_db().trials.find_one({"_id": _oid(trial_id)})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return _out(doc)


@router.put("/{trial_id}", response_model=DocTrialOut)
def update_trial(trial_id: str, body: DocTrialUpdate):
    changes = {k: (v.value if hasattr(v, "value") else v)
               for k, v in body.model_dump(exclude_unset=True).items()}
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")
    if changes.get("title", "x") is None:
        raise HTTPException(status_code=422, detail="title cannot be null")
    changes["updated_at"] = _now()
    doc = get_db().trials.find_one_and_update({"_id": _oid(trial_id)}, {"$set": changes},
                                              return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return _out(doc)


@router.delete("/{trial_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trial(trial_id: str):
    result = get_db().trials.delete_one({"_id": _oid(trial_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
