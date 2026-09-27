from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Trial(Base):
    __tablename__ = "trials"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trial_title = Column(String(255), nullable=False)  # primary field
    sponsor = Column(String(255), nullable=False)      # secondary field
    notes = relationship("TrialNote", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
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