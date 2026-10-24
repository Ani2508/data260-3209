"""HW7 migration: move the MySQL users table to username + role and seed 3 role users.

Idempotent and non-destructive: existing HW4 rows are kept (username = their
email, role = reader). Passwords come from .env (HW7_DEMO_PASSWORD) and only
bcrypt hashes are written.  Run:  python migrate_hw07.py
"""
from __future__ import annotations

import os

from sqlalchemy import inspect, text

import models  # noqa: F401  (registers tables)
from database import Base, SessionLocal, engine
from models import ROLES, User
from security import hash_password, verify_password

PREFIX = "s3209"
DEMO_USERS = {f"{PREFIX}_{role}": role for role in ROLES}  # s3209_reader / _writer / _moderator


def migrate_schema() -> list[str]:
    """Return the list of ALTER statements applied to bring users up to the HW7 shape."""
    applied: list[str] = []
    insp = inspect(engine)
    if not insp.has_table("users"):
        Base.metadata.create_all(bind=engine, tables=[User.__table__])
        return ["CREATE TABLE users"]
    info = {c["name"]: c for c in insp.get_columns("users")}
    cols = set(info)
    steps = []
    if "username" not in cols:
        steps += ["ALTER TABLE users ADD COLUMN username VARCHAR(100) NULL AFTER id",
                  "UPDATE users SET username = LEFT(email, 100) WHERE username IS NULL",
                  "ALTER TABLE users MODIFY username VARCHAR(100) NOT NULL",
                  "ALTER TABLE users ADD UNIQUE INDEX uq_users_username (username)"]
    if "role" not in cols:
        enum = ", ".join(f"'{r}'" for r in ROLES)
        steps.append(f"ALTER TABLE users ADD COLUMN role ENUM({enum}) NOT NULL "
                     "DEFAULT 'reader' AFTER password_hash")
    if "created_at" not in cols:
        steps.append("ALTER TABLE users ADD COLUMN created_at DATETIME NOT NULL "
                     "DEFAULT CURRENT_TIMESTAMP")
    if "name" in cols and not info["name"]["nullable"]:
        steps.append("ALTER TABLE users MODIFY name VARCHAR(100) NULL")
    if "email" in cols and not info["email"]["nullable"]:
        steps.append("ALTER TABLE users MODIFY email VARCHAR(255) NULL")
    with engine.begin() as conn:
        for sql in steps:
            conn.execute(text(sql))
            applied.append(sql)
    return applied


def seed_users(password: str) -> list[dict]:
    """Return the seeded demo users after creating or updating them."""
    db = SessionLocal()
    try:
        for username, role in DEMO_USERS.items():
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                db.add(User(username=username, role=role, password_hash=hash_password(password)))
            else:
                user.role = role
                if not verify_password(password, user.password_hash):
                    user.password_hash = hash_password(password)
        db.commit()
        return [{"id": u.id, "username": u.username, "role": u.role,
                 "password_hash": u.password_hash[:20] + "..."}
                for u in db.query(User).filter(User.username.in_(DEMO_USERS)).order_by(User.id)]
    finally:
        db.close()


if __name__ == "__main__":
    demo_password = os.getenv("HW7_DEMO_PASSWORD", "")
    if len(demo_password) < 8:
        raise SystemExit("Set HW7_DEMO_PASSWORD (8+ characters) in .env before running.")
    for stmt in migrate_schema() or ["(schema already up to date)"]:
        print("schema:", stmt)
    print(f"{'id':>4}  {'username':<18} {'role':<10} password_hash (bcrypt, truncated)")
    for row in seed_users(demo_password):
        print(f"{row['id']:>4}  {row['username']:<18} {row['role']:<10} {row['password_hash']}")
    with engine.connect() as conn:
        if engine.dialect.name == "mysql":
            print("\n" + conn.execute(text("SHOW CREATE TABLE users")).one()[1])
