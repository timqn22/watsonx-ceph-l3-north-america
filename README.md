# TrackerAssist

An AI-powered assistant for Redmine + GitHub workflows, built for the IBM
watsonx challenge. It scrapes open Redmine issues and open GitHub pull requests,
embeds them with **IBM Granite** (via watsonx.ai), and surfaces
likely-but-missing **PR ↔ tracker links** — so managers can catch unlinked PRs,
cut duplicate work, and keep trackers up to date.

The project lives in **[`backend/`](./backend)** — a FastAPI service with the
scraping, embedding, and linkage pipeline. Start with
**[`backend/README.md`](./backend/README.md)**.

## Quick demo (pre-built database — no scraping needed)

**Step 1** — Get the `trackerassist.db` file from Emily (shared via Drive/Slack) and place it at `backend/trackerassist.db`.

**Step 2** — Clone and install (Python 3.11 or 3.12 recommended):

```bash
git clone https://github.com/timqn22/watsonx-ceph-l3-north-america.git
cd watsonx-ceph-l3-north-america
git checkout emi-test-branch
cd backend
pip install -r requirements.txt
pip install sentence-transformers
```

**Step 3** — Create `backend/.env` with these exact contents (no changes needed):

```
EMBEDDER_BACKEND=local
LOCAL_EMBED_MODEL=ibm-granite/granite-embedding-278m-multilingual
RERANK_ENABLED=false
MAX_ISSUES=0
MAX_PULLS=0
```

**Step 4** — Start the server:

```bash
cd backend
uvicorn app.main:app --reload
```

Open http://localhost:8000/health — `issues` count should be above zero.

**Step 5** — Load the extension: go to `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select the `extension/` folder.

**Step 6** — Visit any Ceph issue, e.g. https://tracker.ceph.com/issues/68000 — the TrackerAssist panel appears at the top of the page.

## Quick start (from scratch)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                       # passing, no credentials needed
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

## Features

- **PR ↔ tracker linkage** (`/dashboard`): scrape → Granite embeddings → ranked
  missing-link suggestions with an Accept/Ignore review queue.
- **Personalized task recommendations** (`/recommend`): describe your skills and
  previous projects, get open issues ranked by fit — same Granite embedder, no
  extra model. Per-user profiles; already-in-progress work is excluded.
- **Browser extension** ([`extension/`](./extension)): a Manifest V3 extension
  that injects both features directly onto Redmine pages — a "Related pull
  requests" panel on issue pages and a "Recommended for you" panel (with a
  priority dropdown) on issue listings. No build step; load unpacked.

## Roadmap

- A natural-language "why" for recommendations via a Granite *instruct* model.
- Configurable Redmine host support in the extension beyond tracker.ceph.com.
