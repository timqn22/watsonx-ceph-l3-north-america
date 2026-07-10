# TrackerAssist

An AI-powered assistant for Redmine + GitHub workflows, built for the IBM
watsonx challenge. It scrapes open Redmine issues and open GitHub pull requests,
embeds them with **IBM Granite** (via watsonx.ai), and surfaces
likely-but-missing **PR ↔ tracker links** — so managers can catch unlinked PRs,
cut duplicate work, and keep trackers up to date.

The project lives in **[`backend/`](./backend)** — a FastAPI service with the
scraping, embedding, and linkage pipeline. Start with
**[`backend/README.md`](./backend/README.md)**.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                       # 6 passing, no credentials needed
uvicorn app.main:app --reload
curl localhost:8000/health
```

Or run everything with Docker:

```bash
docker compose up --build    # http://localhost:8000/health
```

## How it runs anywhere

Every external dependency has a graceful fallback, so the whole flow boots and
tests with **no credentials and no network**, then auto-upgrades when you add
real keys:

| Concern    | Real backend      | Fallback (no creds)                                  |
|------------|-------------------|------------------------------------------------------|
| Embeddings | watsonx Granite   | sentence-transformers, then a numpy hash embedder    |
| Store      | any SQLAlchemy DB | local SQLite file (default)                           |
| Issues     | Redmine REST API  | ingest a folder of raw `*.json` issues               |

See [`backend/DECISIONS.md`](./backend/DECISIONS.md) for the reasoning behind
the stack choices.

## Roadmap

- **Now:** PR ↔ tracker linkage suggestions (scrape → Granite embeddings → match).
- **Next:** personalized task recommendations (skill profiles + Granite instruct
  model) reusing the same issue substrate.
- **Then:** a Manifest V3 browser extension that overlays these panels directly
  on Redmine pages, plus a manager review dashboard.
