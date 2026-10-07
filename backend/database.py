"""Database connection (SQLite by default, any SQLAlchemy URL via DB_URL)."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_URL = os.environ.get("DB_URL", f"sqlite:///{os.path.join(BACKEND_DIR, 'orders.db')}")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
