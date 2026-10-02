from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from database import Base

TRIAL_STATUSES = ("Recruiting", "Active - Not Recruiting", "Completed", "Terminated")


class Sponsor(Base):
    """Related entity (the "author" role): one sponsor runs many trials."""
    __tablename__ = "sponsors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)                  # primary text field
    country = Column(String(100), nullable=False)               # secondary text field
    contact_email = Column(String(255), nullable=False, unique=True)  # unique field
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(),
                        onupdate=func.now())

    # No cascade: a sponsor that still has trials cannot be deleted (RESTRICT).
    trials = relationship("Trial", back_populates="sponsor", passive_deletes="all")


class Trial(Base):
    """Primary domain entity: one clinical trial listing."""
    __tablename__ = "trials"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trial_title = Column(String(255), nullable=False)           # primary field
    nct_id = Column(String(11), nullable=False, unique=True)    # unique code, e.g. NCT01234567
    enrollment_slots = Column(Integer, nullable=False, default=0,
                              server_default="0")              # numeric field, default 0
    status = Column(String(40), nullable=False, default="Recruiting",
                    server_default="Recruiting")
    sponsor_id = Column(Integer, ForeignKey("sponsors.id", ondelete="RESTRICT"),
                        nullable=False, index=True)             # foreign key
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(),
                        onupdate=func.now())

    sponsor = relationship("Sponsor", back_populates="trials")
    notes = relationship("TrialNote", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)   # bcrypt hash, never plain text
    sessions = relationship("UserSession", back_populates="user",
                            cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "sessions"
    id = Column(String(64), primary_key=True)  # opaque session token
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    user = relationship("User", back_populates="sessions")


class TrialNote(Base):
    __tablename__ = "trial_notes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trial_id = Column(Integer, ForeignKey("trials.id", ondelete="CASCADE"), nullable=False)
    note_text = Column(String(255), nullable=False)
