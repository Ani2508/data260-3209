"""Pydantic request/response schemas for sponsors and trials (HW5 Part 1)."""
import re
from datetime import datetime
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
NCT_RE = re.compile(r"^NCT\d{8}$")
Status = Literal["Recruiting", "Active - Not Recruiting", "Completed", "Terminated"]


def _not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


# ---------------- Sponsor (related entity) ----------------
class SponsorIn(BaseModel):
    name: str = Field(min_length=1, max_length=255, examples=["Stanford Medicine"])
    country: str = Field(min_length=1, max_length=100, examples=["USA"])
    contact_email: str = Field(max_length=255, examples=["trials@stanford.edu"])

    _strip = field_validator("name", "country")(_not_blank)

    @field_validator("contact_email")
    @classmethod
    def check_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("contact_email must look like name@domain.com")
        return value


class SponsorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    country: str
    contact_email: str
    created_at: datetime
    updated_at: datetime


# ---------------- Trial (primary entity) ----------------
class TrialIn(BaseModel):
    trial_title: str = Field(min_length=1, max_length=255,
                             examples=["Phase II Study of Drug X in Type 2 Diabetes"])
    nct_id: str = Field(examples=["NCT01234567"])
    enrollment_slots: int = Field(default=0, ge=0, le=100000)
    status: Status = "Recruiting"
    sponsor_id: int = Field(gt=0)

    _strip = field_validator("trial_title")(_not_blank)

    @field_validator("nct_id")
    @classmethod
    def check_nct(cls, value: str) -> str:
        value = value.strip().upper()
        if not NCT_RE.match(value):
            raise ValueError("nct_id must be 'NCT' followed by 8 digits, e.g. NCT01234567")
        return value


class TrialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trial_title: str
    nct_id: str
    enrollment_slots: int
    status: str
    sponsor_id: int
    sponsor_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
