"""Test fixtures.

Everything runs against a throwaway SQLite file with the deterministic
HashEmbedder, so tests need no network, no watsonx credentials, and no extra
packages beyond the core requirements.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Configure the app BEFORE importing anything that reads settings.
_TMP_DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["EMBEDDER_BACKEND"] = "hash"

from app.db import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture()
def session():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        yield s
    Base.metadata.drop_all(bind=engine)
