"""Database engine and session management.

Uses SQLAlchemy 2.0 with a SQLite default so the whole stack runs with no
external services. Swapping to Postgres is a one-line change to DATABASE_URL.
Vector similarity is computed in Python (see app.ai.linkage) rather than in the
database, which keeps storage portable at hackathon scale.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


settings = get_settings()

# check_same_thread is a SQLite-only concern; harmless to pass conditionally.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _sqlite_add_missing_columns() -> None:
    """Tiny best-effort migration: add columns introduced after a DB was created.

    Avoids forcing a full re-scrape just to gain a new nullable column. Only
    runs for SQLite; for other backends use a real migration tool.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    # (table, column, type) tuples to ensure exist.
    wanted = [
        ("user_profiles", "background", "TEXT"),
        ("issues", "referenced_pr_numbers", "TEXT"),
        ("issues", "embedded_model", "TEXT"),
        ("pull_requests", "embedded_model", "TEXT"),
    ]
    with engine.begin() as conn:
        for table, column, coltype in wanted:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            existing = {r[1] for r in rows}
            if rows and column not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"
                )


def init_db() -> None:
    """Create all tables. Safe to call repeatedly (idempotent)."""
    # Import models so they register on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _sqlite_add_missing_columns()


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
