"""PyMongo connection + collection setup for s3209_doc (HW6 Parts 1-2)."""
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid

import config

_client = None

# Database-level validation for the document view of a clinical trial
TRIAL_STATUSES = ["recruiting", "active", "completed", "suspended", "withdrawn"]
TRIAL_PHASES = ["phase_1", "phase_2", "phase_3", "phase_4", "observational"]

TRIALS_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["title", "status", "phase", "start_date", "created_at", "updated_at"],
    "properties": {
        "title": {"bsonType": "string", "minLength": 1, "maxLength": 100},
        "description": {"bsonType": ["string", "null"], "maxLength": 2000},
        "status": {"enum": TRIAL_STATUSES},
        "phase": {"enum": TRIAL_PHASES},
        "start_date": {"bsonType": "date"},
        "created_at": {"bsonType": "date"},
        "updated_at": {"bsonType": "date"},
    },
}}

MESSAGES_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["user_id", "session_id", "role", "content", "created_at"],
    "properties": {
        "user_id": {"bsonType": "string"},
        "session_id": {"bsonType": "string"},
        "role": {"enum": ["user", "assistant"]},
        "content": {"bsonType": "string"},
        "created_at": {"bsonType": "date"},
    },
}}

SUMMARIES_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["user_id", "scope", "text", "created_at"],
    "properties": {
        "user_id": {"bsonType": "string"},
        "session_id": {"bsonType": ["string", "null"]},
        "scope": {"enum": ["session", "user"]},
        "text": {"bsonType": "string"},
        "created_at": {"bsonType": "date"},
    },
}}

EPISODES_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["user_id", "session_id", "fact", "importance", "embedding", "created_at"],
    "properties": {
        "user_id": {"bsonType": "string"},
        "session_id": {"bsonType": "string"},
        "fact": {"bsonType": "string", "maxLength": 300},
        "importance": {"bsonType": ["double", "int"], "minimum": 0, "maximum": 1},
        "embedding": {"bsonType": "array", "items": {"bsonType": "double"}},
        "created_at": {"bsonType": "date"},
    },
}}


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000, tz_aware=False)
    return _client


def get_db():
    return get_client()[config.MONGO_DB]


def _ensure(db, name, validator):
    try:
        db.create_collection(name, validator=validator)
    except CollectionInvalid:                      # already exists -> refresh rules
        db.command("collMod", name, validator=validator)


def init_db():
    """Create collections, validators and indexes (idempotent)."""
    db = get_db()
    _ensure(db, "trials", TRIALS_VALIDATOR)
    _ensure(db, "messages", MESSAGES_VALIDATOR)
    _ensure(db, "summaries", SUMMARIES_VALIDATOR)
    _ensure(db, "episodes", EPISODES_VALIDATOR)
    db.trials.create_index([("status", ASCENDING), ("start_date", ASCENDING)])
    db.messages.create_index([("user_id", ASCENDING), ("session_id", ASCENDING), ("created_at", DESCENDING)])
    db.summaries.create_index([("user_id", ASCENDING), ("scope", ASCENDING), ("created_at", DESCENDING)])
    db.episodes.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    return db
