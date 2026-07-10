"""Admin rescrape endpoint returns cleanly (regression: response validation).

The bug: the handler returned a bool `full` under a `dict[str, str]` annotation,
so FastAPI's response validation 500'd. These tests lock the contract.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client(monkeypatch):
    # Stub the background task so no scraping/network happens during the test.
    import app.api as api

    monkeypatch.setattr(api, "run_source", lambda *a, **k: None)
    from app.main import create_app

    # No context manager -> lifespan (scheduler/startup scrape) does not run.
    return TestClient(create_app())


def test_rescrape_full_flag_serializes(monkeypatch):
    r = _client(monkeypatch).post(
        "/admin/rescrape", json={"source": "redmine_open", "full": True}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "redmine_open"
    assert body["full"] is True


def test_rescrape_defaults_full_false(monkeypatch):
    r = _client(monkeypatch).post("/admin/rescrape", json={"source": "github_open"})
    assert r.status_code == 200
    assert r.json()["full"] is False


def test_rescrape_rejects_bad_source(monkeypatch):
    r = _client(monkeypatch).post("/admin/rescrape", json={"source": "nope"})
    assert r.status_code == 422
