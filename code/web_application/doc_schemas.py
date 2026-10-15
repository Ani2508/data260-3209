"""Pydantic schemas for the MongoDB document API and the memory chat API (HW6)."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrialStatus(str, Enum):
    recruiting = "recruiting"
    active = "active"
    completed = "completed"
    suspended = "suspended"
    withdrawn = "withdrawn"


class TrialPhase(str, Enum):
    phase_1 = "phase_1"
    phase_2 = "phase_2"
    phase_3 = "phase_3"
    phase_4 = "phase_4"
    observational = "observational"


def _not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class DocTrialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100, examples=["Metformin XR in Type 2 Diabetes"])
    description: Optional[str] = Field(default=None, max_length=2000)
    status: TrialStatus = TrialStatus.recruiting          # enum with default
    phase: TrialPhase                                      # fixed set of options
    start_date: datetime                                   # ISO 8601 date/time

    _strip = field_validator("title")(_not_blank)


class DocTrialUpdate(BaseModel):
    """PUT body: same rules, every field optional (only sent fields change)."""
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[TrialStatus] = None
    phase: Optional[TrialPhase] = None
    start_date: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value):
        return None if value is None else _not_blank(value)


class DocTrialOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: TrialStatus
    phase: TrialPhase
    start_date: datetime
    created_at: datetime
    updated_at: datetime


# ---------------- memory chat ----------------
class ChatIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    session_id: Optional[str] = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=4000)
    # experiment overrides (Part 3); defaults come from config
    short_term_n: Optional[int] = Field(default=None, ge=0, le=200)
    policy: Optional[str] = Field(default=None, pattern="^(none|compress)$")


class EpisodeOut(BaseModel):
    fact: str
    importance: float
    score: Optional[float] = None


class ChatOut(BaseModel):
    reply: str
    session_id: str
    used: dict
    usage: dict
    new_episodes: List[EpisodeOut] = []
