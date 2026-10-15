"""Route handlers: memory chat endpoints (HW6 Part 2)."""
import uuid

from fastapi import APIRouter

import memory_logic as mem
from doc_schemas import ChatIn, ChatOut
from mongo_db import get_db

router = APIRouter(prefix="/api", tags=["memory chat"])


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    session_id = body.session_id or f"sess-{uuid.uuid4().hex[:8]}"
    return mem.chat_turn(get_db(), body.user_id, session_id, body.message,
                         short_term_n=body.short_term_n, policy=body.policy)


@router.get("/memory/{user_id}")
def memory(user_id: str):
    db = get_db()
    msgs = list(db.messages.find({"user_id": user_id}, {"_id": 0, "user_id": 0})
                .sort([("created_at", -1), ("_id", -1)]).limit(16))
    sess = db.summaries.find_one({"user_id": user_id, "scope": "session"}, {"_id": 0},
                                 sort=[("created_at", -1)])
    life = db.summaries.find_one({"user_id": user_id, "scope": "user"}, {"_id": 0},
                                 sort=[("created_at", -1)])
    eps = list(db.episodes.find({"user_id": user_id}, {"_id": 0, "embedding": 0, "user_id": 0})
               .sort("created_at", -1).limit(20))
    return {"user_id": user_id, "recent_messages": list(reversed(msgs)),
            "session_summary": sess, "lifetime_summary": life, "episodic_facts": eps}


@router.get("/aggregate/{user_id}")
def aggregate(user_id: str):
    db = get_db()
    daily = list(db.messages.aggregate([
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "messages": {"$sum": 1},
                    "user_messages": {"$sum": {"$cond": [{"$eq": ["$role", "user"]}, 1, 0]}}}},
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "date": "$_id", "messages": 1, "user_messages": 1}},
    ]))
    recent = list(db.summaries.find({"user_id": user_id}, {"_id": 0, "user_id": 0})
                  .sort("created_at", -1).limit(5))
    return {"user_id": user_id, "daily_message_counts": daily, "recent_summaries": recent}
