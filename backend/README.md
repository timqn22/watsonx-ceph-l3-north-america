# TrackerAssist — backend

AI-powered **PR ↔ tracker linkage** for Redmine + GitHub, built for the IBM
watsonx challenge. It scrapes open Redmine issues and open GitHub pull requests,
embeds them with **IBM Granite** (via watsonx.ai), and surfaces
likely-but-missing links so managers can catch unlinked PRs and reduce
duplicate work.

This is Phase 1–2 of the plan: scraping + embeddings + linkage, exposed over a
FastAPI service. The browser extension and the personalized task-recommendation
feature build on this same substrate next.

## Why it runs anywhere

Every external dependency has a graceful fallback, so you can boot and demo the
whole flow with **no credentials and no network**:

| Concern    | Real backend                    | Fallback (no creds)                     |
|------------|---------------------------------|-----------------------------------------|
| Embeddings | watsonx Granite                 | `sentence-transformers`, then a numpy hash embedder |
| Store      | any SQLAlchemy DB               | local SQLite file (default)             |
| Issues     | Redmine REST API                | ingest the prototype's `raw_issues/*.json` |

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional: fill in credentials
uvicorn app.main:app --reload
```

Then:

```bash
curl localhost:8000/health
curl localhost:8000/suggestions/links/unlinked | jq
```

On startup it runs one scrape+embed+match cycle immediately, then repeats on a
schedule (open items every 15 min, closed every 6 h).

With **zero config** it uses the hash embedder against SQLite and will try to
scrape `tracker.ceph.com` anonymously. To use real Granite embeddings, set the
`WATSONX_*` vars in `.env` (see `.env.example`) — the app auto-switches.

## Run the tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

Tests use the deterministic hash embedder against a throwaway SQLite DB — no
network, no credentials, no model downloads.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | status, counts, active embedder, scheduled jobs |
| GET  | `/issues?limit=` | most-recently-updated issues |
| GET  | `/pulls?limit=` | most-recently-updated PRs |
| GET  | `/suggestions/links/unlinked?min_similarity=&limit=` | manager review queue |
| GET  | `/suggestions/links/for-issue/{id}` | suggested PRs for one issue |
| GET  | `/suggestions/links/for-pr/{id}` | suggested issues for one PR |
| POST | `/suggestions/links/{id}/decision` | `{status: accepted\|rejected\|ignored}` |
| POST | `/admin/rescrape` | `{source: redmine_open\|...}` force one cycle (demos) |

## Layout

```
backend/app
  config.py          settings (pydantic-settings)
  db.py  models.py   SQLAlchemy engine + ORM
  schemas.py         pydantic API contracts
  api.py             FastAPI routes
  main.py            app factory + lifespan
  scheduler.py       APScheduler periodic jobs
  text.py            payload normalization + #ref parsing
  clients/           redmine.py, github.py  (HTTP)
  ai/                embedder.py (Granite/local/hash), linkage.py (matching)
  services/          scraper.py, indexer.py, pipeline.py
```

See [`DECISIONS.md`](./DECISIONS.md) for the reasoning behind the stack choices.
