"""The /health endpoint responds (regression: it referenced an unimported name)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(session):
    # `session` fixture creates the tables on the shared engine.
    from app.main import create_app

    client = TestClient(create_app())  # no lifespan -> no scheduler/scrape
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "status", "db_ok", "embedder", "reranker", "issues", "jobs",
        "snapshot_cache", "embed_cache",
    ):
        assert key in body
