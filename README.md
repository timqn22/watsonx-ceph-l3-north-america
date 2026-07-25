# TrackerAssist

An AI-powered assistant for Redmine + GitHub workflows, built for the IBM watsonx challenge. It scrapes open Redmine issues and open GitHub pull requests, embeds them with **IBM Granite** (`ibm-granite/granite-embedding-278m-multilingual`), and surfaces two features from one shared index:

1. **PR ↔ tracker linkage** — catches unlinked PRs and flags duplicate work before it happens.
2. **Personalized task recommendations** — ranks open, available issues by fit to your skills and history.

Both features are surfaced directly on Redmine pages via a lightweight browser extension. No separate tab needed.

---

## Quick demo (pre-built database — no scraping needed)

> Get the `trackerassist.db` file from Emily (shared via Drive/Slack) and place it at `backend/trackerassist.db`.

**Step 1** — Clone and install (**Python 3.10+ required** — 3.11 or 3.12 recommended):

```bash
python3 --version   # must be 3.10 or higher

git clone https://github.com/timqn22/watsonx-ceph-l3-north-america.git
cd watsonx-ceph-l3-north-america
git checkout emi-test-branch
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install sentence-transformers
```

**Step 2** — Create `backend/.env` with these exact contents (no changes needed):

```
EMBEDDER_BACKEND=local
LOCAL_EMBED_MODEL=ibm-granite/granite-embedding-278m-multilingual
RERANK_ENABLED=false
MAX_ISSUES=0
MAX_PULLS=0
```

**Step 3** — Start the server:

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000/health — `issues` count should be above zero.

**Step 4** — Load the extension:

1. Go to `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select the `extension/` folder.
2. Visit any Ceph issue, e.g. https://tracker.ceph.com/issues/68000 — the TrackerAssist panel appears at the top.

---

## Quick start (from scratch)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                        # all tests pass, no credentials needed
uvicorn app.main:app --reload
curl localhost:8000/health
```

Or with Docker:

```bash
docker compose up --build     # http://localhost:8000/health
```

On startup, one scrape+embed+match cycle runs immediately, then repeats on a schedule (open items every 15 min, closed every 6 h).

---

## How it runs anywhere

Every external dependency has a graceful fallback — the whole app boots and tests with **no credentials and no network**, then auto-upgrades when you add real keys:

| Concern    | Real backend              | Fallback (no creds)                                               |
|------------|---------------------------|-------------------------------------------------------------------|
| Embeddings | watsonx Granite (managed) | Granite run locally via `sentence-transformers`, then a hash embedder |
| Store      | any SQLAlchemy DB         | local SQLite file (default)                                       |
| Issues     | Redmine REST API          | ingest a folder of raw `*.json` issues (`RAW_ISSUES_DIR`)         |

> **No watsonx account?** `pip install sentence-transformers` and the app runs IBM's open Granite embedding model locally — same model, no API quota. Set `EMBEDDER_BACKEND=local` in `.env`. The watsonx path stays available for managed/production hosting.

---

## Features

### PR ↔ tracker linkage

The **Related pull requests** panel appears on every issue page. It detects links from both directions:

- *PR → tracker*: parses `#1234` and `tracker.ceph.com/issues/1234` URLs from the PR body.
- *tracker → PR*: parses GitHub PR URLs and the "Pull request ID" field from the issue description and custom fields.

If a confirmed link exists, it shows only that (marked **Linked**, with a flag if the back-reference is missing). If no link exists, it shows **possible matches** — PRs ranked by Granite cosine similarity — each with a calibrated confidence bar.

The confidence is calibrated: Ceph issues and PRs share enough jargon that unrelated pairs already score ~0.7 raw, so we subtract that baseline — a raw 0.77 shows as an honest modest confidence, not a misleading "77%."

### Manager dashboard

Open **http://localhost:8000/dashboard** for the manager view:

- Coverage stats across all projects.
- The ranked missing-link queue with Accept / Ignore buttons. Decisions are preserved across scrape cycles.
- **Unassigned — already being worked on**: open, unassigned issues where an open PR is already in flight (via reference or cosine ≥ 0.82). Catches duplicate work before it happens.

Set `DASHBOARD_TOKEN` in `.env` to require `?token=<value>`; leave blank for an open page on localhost.

### Personalized task recommendations

The **Recommended for you** panel appears on issue listings and My Page. It ranks open, unassigned, not-in-progress issues by cosine similarity to your profile vector — same Granite embedder, no extra model or quota.

**You don't have to fill in anything.** The extension reads your logged-in Redmine identity, fetches your authored/assigned issues, and builds a profile automatically. Use the popup to refine skills in free text, or click **Rebuild from my activity** to refresh it.

Filters (project, tracker type, priority) narrow the candidate pool; ranking still comes from your profile. Stretch picks — solid issues slightly outside your core area — are mixed in to encourage growth.

### Duplicate tracker detection

The **Duplicate Tracker Detection** panel (in the extension's collapsible section) finds groups of trackers with near-identical embeddings (cosine ≥ 0.92 by default). Groups are formed as cliques — every member must be mutually similar, not just similar to the seed — so related-but-distinct issues don't get bundled together.

A ⚠ **Possible duplicate** warning also appears on individual issue pages when a near-identical tracker already exists.

---

## Browser extension

A Manifest V3 extension — no build step, plain JavaScript. Load it unpacked:

1. `chrome://extensions` (or `edge://extensions`) → **Developer mode** → **Load unpacked** → select `extension/`.
2. Click the toolbar icon to open the popup:
   - **Backend URL** — e.g. `http://localhost:8000`.
   - **Your ID** — any handle (e.g. `eleson`). Auto-detected from your Redmine login if left blank.
   - Optionally fill in **Skills**, **Previous projects**, preferred projects/trackers → **Save profile**.
3. Visit any page on `tracker.ceph.com` — panels appear at the top of the content area.

**To use a different Redmine host:** add it to `host_permissions` and `content_scripts.matches` in `extension/manifest.json`, then reload the extension.

**"Backend offline" error:** check the Backend URL in the popup and confirm the server is running.

Firefox is out of scope (Manifest V3 background-worker differences).

---

## API reference

| Method   | Path                                          | Purpose                                                    |
|----------|-----------------------------------------------|------------------------------------------------------------|
| GET      | `/health`                                     | status, counts, active embedder, scheduled jobs            |
| GET      | `/issues?limit=`                              | most-recently-updated issues                               |
| GET      | `/pulls?limit=`                               | most-recently-updated PRs                                  |
| GET      | `/suggestions/links/unlinked`                 | manager review queue                                       |
| GET      | `/suggestions/links/for-issue/{id}`           | suggested PRs for one issue                                |
| GET      | `/suggestions/links/for-pr/{id}`              | suggested issues for one PR                                |
| POST     | `/suggestions/links/{id}/decision`            | `{status: accepted\|rejected\|ignored}`                    |
| GET      | `/issues/in-progress?unassigned_only=`        | open issues a PR is already working on                     |
| GET      | `/duplicates/detect?min_similarity=&limit=`   | groups of near-duplicate trackers                          |
| GET/PUT  | `/profiles/me`                                | read/update skill profile                                  |
| POST     | `/recommendations/issues`                     | rank open issues by fit to a skill description             |
| GET      | `/dashboard`                                  | manager review queue as a web page                         |
| GET      | `/recommend`                                  | skill-based task recommendation page                       |
| POST     | `/admin/rescrape`                             | `{source: redmine_open\|...}` force one cycle (demos)      |

---

## Configuration

All settings load from `backend/.env` (or environment variables). Defaults boot with zero config.

| Variable                    | Default                                      | Notes                                           |
|-----------------------------|----------------------------------------------|-------------------------------------------------|
| `DATABASE_URL`              | `sqlite:///./trackerassist.db`               | switch to Postgres with one line                |
| `REDMINE_URL`               | `https://tracker.ceph.com`                   |                                                 |
| `REDMINE_API_KEY`           | —                                            | anonymous scraping works without it             |
| `GITHUB_TOKEN`              | —                                            | required for private repos; boosts rate limits  |
| `GITHUB_REPOS`              | `ceph/ceph`                                  | comma-separated list                            |
| `WATSONX_API_KEY`           | —                                            |                                                 |
| `WATSONX_PROJECT_ID`        | —                                            |                                                 |
| `EMBEDDER_BACKEND`          | `auto`                                       | `auto` \| `watsonx` \| `local` \| `hash`        |
| `LOCAL_EMBED_MODEL`         | `ibm-granite/granite-embedding-278m-multilingual` | used when `EMBEDDER_BACKEND=local`         |
| `DUPLICATE_MIN_SIMILARITY`  | `0.92`                                       | raise to reduce false positives                 |
| `LINK_MIN_SIMILARITY`       | `0.72`                                       | minimum cosine for PR↔issue suggestions         |
| `DASHBOARD_TOKEN`           | —                                            | require `?token=` on `/dashboard`; blank = open |
| `ADMIN_TOKEN`               | —                                            | require token on `POST /admin/rescrape`         |

---

## Project layout

```
backend/app/
  config.py          settings (pydantic-settings, loads .env)
  db.py  models.py   SQLAlchemy engine + ORM models
  schemas.py         pydantic API contracts
  api.py             FastAPI routes
  main.py            app factory + lifespan
  scheduler.py       APScheduler periodic jobs
  text.py            payload normalisation + #ref parsing
  clients/           redmine.py, github.py  (HTTP clients)
  ai/                embedder.py, linkage.py, index_cache.py
  services/          scraper.py, indexer.py, pipeline.py, recommendations.py

extension/
  manifest.json      Manifest V3 config
  content.js         injected panels (linkage, recommendations, duplicates)
  content.css        panel styles
  popup.html/js      toolbar popup (settings, profile, duplicate list)
  background.js      service worker
```

---

## Design notes

**SQLite + numpy cosine (not Postgres + pgvector):** runs anywhere with zero external services — `pip install && uvicorn`, no Docker required. At this scale (thousands of issues/PRs) a full cosine matmul is effectively instant; the storage layer is behind SQLAlchemy, so switching `DATABASE_URL` to Postgres is a one-line change.

**In-memory snapshot cache:** embeddings are loaded from SQLite once per scrape cycle into a float32 numpy matrix (`index_cache.py`). All similarity searches — linkage, recommendations, duplicate detection — are matmuls against that cached matrix. Rebuilt automatically after each scrape; hit/miss stats on `/health`.

**Re-embedding is incremental:** each row stores a `content_hash`. The indexer only re-embeds rows where the hash changed — unchanged issues/PRs are never re-embedded, keeping watsonx token usage down.

**Calibrated confidence:** Granite similarities among Ceph items sit well above zero even when unrelated (~0.70 baseline from shared jargon). Displayed confidence maps `[0.70..1.0] → [0..100%]` so the number is honest.

**Demo script:** see [`docs/DEMO.md`](./docs/DEMO.md) for the full presenter walkthrough with talking points and Q&A cheat-sheet.
