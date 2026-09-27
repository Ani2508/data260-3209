import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import event

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DB_URL = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "s3209_rel"),
)

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    # Required name: db_session_basede26
    db_session_basede26 = SessionLocal()
    try:
        yield db_session_basede26
    finally:
        db_session_basede26.close()



query_count = {"count": 0}

@event.listens_for(engine, "before_cursor_execute")
def _count_queries(conn, cursor, statement, parameters, context, executemany):
    query_count["count"] += 1