# TrackerAssist — Project Overview

AI assistance for the Ceph project's issue tracker. TrackerAssist connects the
two worlds a Ceph contributor lives in — the **Redmine tracker**
(`tracker.ceph.com`) and **GitHub pull requests** (`ceph/ceph`) — using IBM
Granite embeddings to answer three questions directly on the pages people
already use:

1. **"Which PR implements this tracker?"** (and, for a PR, which tracker it belongs to)
2. **"What open work fits me?"** — personalized, searchable recommendations
3. **"Has this bug already been reported?"** — a duplicate warning when filing

It is a **FastAPI backend** + a **Manifest V3 browser extension**, and it runs
entirely on **free, local IBM Granite embeddings** — no paid watsonx quota
required, though the embedder is pluggable to watsonx.ai when you have it.

---

## 1. Architecture at a glance

```
 Redmine (tracker.ceph.com) ──┐
 GitHub PRs (ceph/ceph) ──────┤
                              ▼
                    ┌─────────────────────┐        ┌──────────────────────────┐
                    │   Scrapers (delta)  │        │  Browser extension (MV3) │
                    │  15 min open /      │        │  injects panels on        │
                    │  6 hr closed        │        │  Redmine issue + list     │
                    └─────────┬───────────┘        │  pages                    │
                              ▼                     └────────────┬─────────────┘
                    ┌─────────────────────┐                      │ HTTP
                    │  SQLite (issues,    │                      ▼
                    │  PRs, embeddings)   │        ┌──────────────────────────┐
                    └─────────┬───────────┘        │       FastAPI API        │
                              ▼                     │  /related-prs /similar   │
                    ┌─────────────────────┐        │  /recommendations ...    │
                    │  Granite embeddings │◀───────┤                          │
                    │  (local, free)      │        └────────────┬─────────────┘
                    └─────────┬───────────┘                     │
                              ▼                                  ▼
                    ┌─────────────────────────────────────────────────────┐
                    │  In-memory snapshot: issue & PR matrices (numpy) +   │
                    │  PR reference index — one matmul per query           │
                    └─────────────────────────────────────────────────────┘
```

---

## 2. Data layer — scraping & storage

- **Sources**: Redmine issues via the Redmine REST API; GitHub PRs via the
  GitHub REST API (token-aware for higher rate limits).
- **Cadence**: a background scheduler (APScheduler) polls **open items every 15
  minutes** and **closed items every 6 hours**. Open work changes fast and
  matters most; closed items are a slow drift-catch.
  > *The 15-minute PR-polling cadence is an idea shared by Aaryan Kumar
  > (see Acknowledgements).*
- **Delta polling**: each source keeps a cursor, so we only fetch what changed
  since last run instead of re-scraping the world.
- **Storage**: SQLite (SQLAlchemy 2.0). Portable, zero external services; a
  one-line change points it at Postgres.
- **Content-hash re-embedding**: each item stores a hash of its embed-text. We
  only recompute an embedding when that text actually changes — so a re-scrape
  is cheap and embeddings never churn needlessly. The embedding model id is also
  stored, so swapping models triggers a clean re-embed.

---

## 3. Embeddings — IBM Granite (the watsonx family), run locally

**Model**: `ibm-granite/granite-embedding-278m-multilingual` — a **768-dimension**,
**278M-parameter** retrieval-tuned embedding model from IBM's Granite family
(the same family exposed through watsonx.ai). We run it **locally** via
`sentence-transformers`, so it's **free and offline** — real Granite, no quota.

**Pluggable backend** (`EMBEDDER_BACKEND`):
- `watsonx` — IBM watsonx.ai Granite (for when quota is available),
- `local` — the local Granite model above (default in practice),
- `hash` — a dependency-free feature-hashing fallback so tests and a first-boot
  demo work with nothing installed.

The whole stack depends only on an `Embedder` interface, so no other layer knows
or cares which backend produced a vector.

### Why Granite here is stronger than the MiniLM baseline

Aaryan's backend embeds with `all-MiniLM-L6-v2` (**384-dim, ~22M params**), a
fast general-purpose sentence model. Granite-278m is a deliberate upgrade for
this task:

| | Aaryan (MiniLM-L6-v2) | TrackerAssist (Granite-278m) |
|---|---|---|
| Dimensions | 384 | **768** (finer-grained similarity) |
| Parameters | ~22M | **278M** (more capacity for technical text) |
| Design | general sentence similarity | **retrieval-tuned**, multilingual |
| Challenge fit | generic | **IBM Granite = the watsonx family** — on-brand |

More dimensions and capacity give sharper separation between the *near-duplicate*
Ceph items (many issues share the same jargon), which is exactly where the ranking
is won or lost. And because it's the Granite family, it fits the watsonx-branded
challenge honestly while still costing nothing to run.

---

## 4. Similarity — cosine, and why we keep it

Every embedding is **L2-normalized to a unit vector** at store time. For unit
vectors, **cosine similarity is just the dot product**, so a whole batch of
comparisons is a single matrix multiply (`issue_matrix @ query_vector`) — instant
even at 64k issues / 70k PRs.

**Calibrated confidence.** Granite similarities among Ceph items sit *well above
zero* even for unrelated pairs, because everything shares Ceph vocabulary — a raw
cosine of 0.77 is not "77% related". So the displayed confidence subtracts a
domain floor (0.70) and rescales `[floor..1] → [0..100%]`. At or below the floor
reads as ~0%. This makes the number honest instead of flattering.

**Why cosine over a heavier scorer**: it's exact, interpretable, and — combined
with the structural signals below — it's what our own evaluation shows works best
on real data (Section 8). We tried the fancier alternative (a cross-encoder
reranker) and *measured* that it made things worse. Cosine + hybrid structure is
not the lazy choice; it's the *measured* choice.

---

## 5. Hybrid scoring — cosine + structure

Cosine content similarity is the base ranker. On top of it we add small, bounded
**structural signals** that encode things embeddings don't reliably capture:

- **Branch-number match** (weight **0.30**): the issue's tracker number appears
  in the PR's head branch (`wip-46912-…`). Near-decisive when present.
- **Component agreement** (weight **0.03**): the PR and issue point at the same
  Ceph subsystem (rbd, rados, cephfs, bluestore, rgw, mgr, …), inferred from
  title prefixes and branch names.
- **Component conflict penalty** (weight **0.05**): clearly-different subsystems
  are pushed apart.

These weights are not guesses — they were **grid-searched against real data**
(Section 8). The search showed the **branch match dominates** and the component
signal is weak, which is why the weights land where they do.

---

## 6. Lexical + semantic search — with IDF

The recommendation panel has a search box that ranks issues by a typed query.
Pure dense (embedding) retrieval has a known blind spot: it ranks by *aboutness*,
so it can **bury an exact title match** under other same-topic issues. Searching
"Measure BlueStore caches' performance" would rank generic bluestore issues over
the one literally titled that.

So search is **hybrid**: `semantic cosine + lexical_weight × (title keyword overlap)`.

- The lexical term is **IDF-weighted** — a rare, distinctive query word
  ("measure") counts far more than a ubiquitous one ("bluestore"). Document
  frequencies are computed once over all issue titles when the snapshot builds.
- `search_lexical_weight` (default 0.5) balances the two halves.

Result: an issue whose title actually contains your words is lifted to the top,
while purely-semantic matches still appear just below.

### Why only IDF — not full TF-IDF / BM25

This lexical idea was **inspired by Aaryan's BM25 search** (BM25 is the TF-IDF
family — term-frequency × inverse-document-frequency, plus saturation and
length-normalization). We deliberately kept **only the IDF portion** and dropped
the rest, for three concrete reasons:

1. **We match on titles, which are short.** BM25's *term-frequency* component
   rewards a word appearing many times in a document. In a one-line issue title a
   term appears **once or not at all** — TF is effectively binary, so it adds no
   signal. The same goes for BM25's document-length normalization: there's
   nothing meaningful to normalize across short titles.
2. **IDF is the part that actually discriminates.** It down-weights words that
   are everywhere in Ceph ("bluestore" is in thousands of issues) and up-weights
   the rare, distinctive ones ("measure", "histogram"). That rare-word weighting
   is precisely what pulls an exact title match above the same-topic crowd — and
   it's the piece BM25 and plain TF-IDF share.
3. **The semantic half already does the heavy lifting.** Dense Granite embeddings
   handle "how related is this document overall" far better than any bag-of-words
   score. So the lexical half doesn't need to *be* a full retrieval model — it
   only needs to catch the exact-keyword case dense retrieval misses. For that,
   IDF-weighted overlap is sufficient, and bolting on full BM25 machinery would be
   complexity and tuning surface (k1, b parameters) for no measurable gain.

In short: we took the one component of his TF-IDF/BM25 approach that carries the
signal for *our* data shape, and let the Granite embeddings own everything TF and
length-normalization would otherwise contribute.

---

## 7. Why we don't ship a reranker

We **built** a cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`,
sigmoid → relevance) as an optional precision stage — the same reranking idea
Aaryan shared (see Acknowledgements). Then we **measured it** with the eval
harness on 34,155 real tracker↔PR links:

| Approach | top-1 |
|---|---|
| Raw Granite cosine | 36.2% |
| **+ hybrid structure (shipped)** | **70.0%** |
| + cross-encoder rerank | 37.9% |

The reranker **dropped accuracy back to near-baseline** (−30 points vs hybrid).
The reason: `ms-marco-MiniLM` was trained to judge *web-search question/passage*
relevance. An issue and its implementing PR don't look like a Q&A pair — they
share subsystem, tracker numbers, and technical vocabulary, which is exactly what
the *hybrid* signals capture and what a Q&A cross-encoder is blind to. Wrong tool
for this domain.

So the reranker code stays in the repo (pluggable, `RERANK_ENABLED=false`) as a
*documented, evaluated* decision — but it is **off**, and cosine + hybrid is what
ships. This is the core of our engineering story: **we test ideas before we trust
them.**

---

## 8. Evaluation & tuning — the rigor

Everything above is backed by a measurement harness, not vibes.

- **`scripts/eval_linkage.py`**: uses every existing `#ref` link between a PR and
  a tracker as **ground truth**, and reports **top-1 / top-3 / MRR** for
  content-only vs hybrid vs hybrid+rerank. Memory-safe by streaming embeddings
  into float32 — runs on the full 64k/70k dataset.
- **`scripts/tune_weights.py`**: grid-searches the structural weights against that
  ground truth. Cosine is computed once per batch and reused across every weight
  combination, so the whole sweep costs about one eval run.

Headline result on real data: **hybrid ≈ 70% top-1, nearly 2× raw embeddings
(36%)**, with the tuned weights `branch=0.30, component=0.03, penalty=0.05`.

---

## 9. Related-PR matching (both directions + two-hop)

For an issue page, the "Related pull requests" panel:

1. **Recorded links win**: if a PR references the tracker (or the tracker
   references the PR via its "Pull request ID" field / a PR URL — *both
   directions*, including links found only in comments), those are shown as
   definite links.
2. **Otherwise, two retrieval paths, blended on one calibrated scale:**
   - **Direct**: the strongest issue→PR content matches (hybrid).
   - **Two-hop**: PRs *recorded as fixing a highly similar tracker*
     (issue↔issue similarity ≥ 0.80) — labeled "via similar tracker #N". This
     leans on the *easy* hop (issue↔issue, where the matcher is strongest) plus a
     known-true link, so it often surfaces better fixes than a direct
     problem→fix jump. Closed siblings count on purpose — a closed similar
     tracker's merged PR is the "how was this solved before" pointer.

All lookups run off a cached PR reference index — O(1), no table scans.

---

## 10. Duplicate warning

When you open a tracker, the panel checks for **near-identical trackers**
(issue↔issue cosine ≥ **0.88**, deliberately high) and, only when there's a hit,
shows an amber "Possible duplicate" box with each sibling's status and similarity.
It stays silent for the vast majority of issues — a duplicate warning is only
trusted if it's right when it speaks. Closed trackers are included: "already
reported and fixed" is the most valuable duplicate to catch.

---

## 11. Personalized recommendations

- **Profile, auto-derived**: no manual entry — the extension signs in with your
  Redmine login and builds your profile from the trackers you've authored/been
  assigned. The popup only *refines* it.
- **Ranking**: cosine of your profile embedding against open issues, plus a small
  **component-affinity boost** so familiar-subsystem work floats up.
- **Relative FIT**: the best available match reads ~100 and weaker ones taper —
  far more intuitive than a bare cosine rendered as a tiny "30%".
- **"Hide claimed" filter**: hides issues that already have an **assignee** or a
  **linked PR** (either direction) — so recommendations are *grabbable* work by
  default. Works in every mode (default, filtered, search) and persists.
- **Filters**: priority, projects, trackers (multi-select), all working alongside
  search.

---

## 12. Performance — the in-memory snapshot

Re-reading and JSON-parsing every embedding from SQLite per request is the real
latency source at scale. So all open/closed embedded issues and open PRs are held
as **numpy matrices in memory** (the "snapshot"), plus a lightweight **PR
reference index** for O(1) linked-PR detection.

- A query is one matrix multiply against an already-loaded array — ~0.01 ms
  lookups after the ~2 s one-time build.
- The snapshot is **invalidated on embedding changes** and **warmed in the
  background** by the scheduler after each scrape, so no user request ever pays
  the rebuild. A 30-minute TTL is just a safety net.
- Scales cleanly to the real corpus: **64k issues / 70k PRs**.

---

## 13. Browser extension

- **Manifest V3**, vanilla JS, **no build step** — load the folder.
- **Cross-browser**: one codebase runs on all Chromium browsers (Chrome, Edge,
  Brave, Opera, …) and **Firefox 121+** (a `browser_specific_settings.gecko`
  block; the code uses only standard WebExtension APIs). Safari needs a one-time
  conversion.
- **Panels**: issue page → related PRs + duplicate warning; issue lists / My page
  → recommendations + search.
- **Resilient API calls**: timeout + auto-retry on transient failures, so the
  cold-start snapshot build doesn't read as "backend offline"; definitive 4xx
  fail fast.
- Holds **no credentials** — just the backend URL and your Redmine handle.

---

## 14. Acknowledgements — ideas shared by Aaryan Kumar

Three backend ideas came from Aaryan's work, and are credited here:

1. **Cross-encoder reranking.** We took the reranking approach from his backend,
   implemented it, and evaluated it against our real links. It didn't help on
   this domain (Section 7), so it ships **disabled** — but the idea, and the
   decision to test it, trace back to him.
2. **The 15-minute PR-polling cadence.** Our scheduler polls open PRs on the same
   ~15-minute window as his PR monitor (Section 2).
3. **Lexical search — the IDF piece.** His BM25 (TF-IDF-family) lexical search
   inspired our hybrid search. We adopted **only the IDF component** — the
   rare-word weighting — and deliberately dropped term-frequency and
   length-normalization, because our lexical signal runs over short titles where
   they add nothing and the Granite embeddings already own document-level
   relevance (Section 6).

In each case we took the *idea*, then made our own call based on our data:
reranking was measured and rejected, and the TF-IDF borrowing was pared down to
just IDF. Everything else was built independently on a different stack (FastAPI +
SQLite + in-memory numpy vs his Flask + ChromaDB), validated with the eval
harness.

---

## 15. Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0, SQLite, APScheduler |
| Embeddings | IBM Granite `granite-embedding-278m-multilingual` (local, free; watsonx.ai-pluggable) |
| Similarity | cosine (unit-vector dot product), numpy |
| Ranking | hybrid: cosine + branch/component structural signals (grid-tuned) |
| Search | hybrid dense + IDF-weighted lexical |
| Extension | Manifest V3, vanilla JS, Chromium + Firefox |
| Evaluation | ground-truth `#ref` links → top-1/top-3/MRR + weight grid-search |
