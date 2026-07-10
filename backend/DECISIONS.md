# Design Decisions

Running log of non-obvious choices, so reviewers (and future prompts) can see
the reasoning instead of re-litigating it.

## Architecture

- **Backend + (future) browser extension**, not a Ruby Redmine plugin. A plugin
  is slow to iterate on and hard to demo; a FastAPI service is fast to build and
  can decorate Redmine pages via an extension later.
- **Two features share one substrate**: a fresh, embedded view of every open
  work item (issues + PRs). Feature A (PR↔tracker linkage) ships first; Feature
  B (personalized task recommendations) reuses the same scraper, embedder, and
  issue table.

## Storage: SQLite + in-Python cosine (was: Postgres + pgvector)

The original plan called for Postgres + pgvector. **Changed to SQLite with
similarity computed in numpy.** Rationale:

- Runs anywhere with zero external services — `pip install && uvicorn`, no
  Docker required. Critical for a hackathon demo on an unknown machine.
- At this scale (thousands of issues/PRs) a full cosine matrix multiply is
  effectively instant; a vector DB is premature.
- The storage layer is behind SQLAlchemy, so switching `DATABASE_URL` to
  Postgres is a one-line change if scale ever demands it. Embeddings are stored
  as JSON arrays, which both backends support.

Trade-off accepted: in-Python search won't scale to millions of rows. Fine for
the challenge; noted for "what's next."

## Embeddings: pluggable, watsonx-first

`app/ai/embedder.py` defines an `Embedder` protocol with three backends and an
`auto` selector:

1. **WatsonxGraniteEmbedder** — real IBM Granite via `ibm-watsonx-ai`. The
   intended demo backend. Model id from `WATSONX_EMBED_MODEL_ID`
   (default `ibm/granite-embedding-278m-multilingual`).
2. **LocalEmbedder** — `sentence-transformers`, offline, no credentials.
3. **HashEmbedder** — deterministic feature-hashing, numpy only, **zero extra
   deps**. Powers tests and a first-boot demo with nothing installed and no
   network. Captures lexical overlap — enough to prove the pipeline.

`auto` picks watsonx if credentials are present, else local if installed, else
hash. All vectors are L2-normalized, so cosine similarity is a dot product.

Embedding **dimension is not hard-coded** — it's whatever the active model
emits (Granite embed models are commonly 384/768; the hash fallback is 512).
Because vectors are stored per-row as JSON and compared pairwise, mixing is
avoided by only ever running one backend per deployment.

## Re-embedding strategy

Each row stores `content_hash` (sha256 of the text) and `embedded_hash`. The
indexer only (re)embeds rows where the embedding is missing or the content hash
has moved. Unchanged issues/PRs are never re-embedded — keeps watsonx token
usage down.

## Linkage matching

- A PR whose body references an existing issue via `#123` is treated as
  **already linked** and excluded as a source of suggestions.
- `LINK_MIN_SIMILARITY` default **0.72** (cosine). Suggestions below it are
  dropped. Tune per real data.
- Suggestions are **cached** in `link_suggestions` and recomputed each cycle
  rather than on every API request. Human decisions
  (accepted/rejected/ignored) are **preserved** across rebuilds — only pending
  rows are regenerated.

## Scraping cadence

- Open issues + open PRs: **every 15 min** (`SYNC_OPEN_MINUTES`).
- Closed items drift catch: **every 6 h** (`SYNC_CLOSED_HOURS`).
- Delta polling via `updated_on` / `updated_at` cursors stored in
  `scrape_state`, so repeated runs only fetch what changed. GitHub's list-pulls
  endpoint can't filter by `updated_at` server-side, so that delta is applied
  client-side (results are sorted updated-desc; we stop past the cursor).
- One open cycle runs immediately on startup so there's data to demo.

## Salvaging the prototype's scrape

If `RAW_ISSUES_DIR` points at the original prototype's `raw_issues/*.json`
dump, `sync_redmine` ingests from disk instead of hitting the Redmine API — so
an existing scrape isn't wasted while iterating on the new stack.

## What's next (not built yet)

- Feature B: skill profiles + Granite-instruct task recommendations.
- Browser extension shell (Manifest V3) overlaying panels on Redmine pages.
- Manager dashboard + coverage metrics.
