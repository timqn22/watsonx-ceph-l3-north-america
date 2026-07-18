"""In-memory snapshot of open issue/PR embeddings.

Loading and JSON-parsing every embedding out of SQLite on each request is the
main latency source at scale (thousands of ~768-float vectors). This caches the
open issues' and PRs' vectors as numpy matrices plus the metadata needed for
filtering, so recommendation and in-progress detection become a single matmul
against an already-loaded array.

Invalidated whenever embeddings change (the indexer calls ``invalidate``) and
otherwise refreshed on a short TTL as a safety net.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
from collections import defaultdict
from types import SimpleNamespace

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import Issue, PullRequest

_LOCK = threading.Lock()
# The cache is invalidated whenever embeddings change (after each scrape cycle),
# so the TTL is just a safety net. Keep it long -- at scale the rebuild is
# multi-second, and the scheduler warms it in the background after each cycle,
# so no user request should ever pay for it.
_TTL_SECONDS = 1800.0
_snapshot: "Snapshot | None" = None
# Observability: how often a request was served from the warm snapshot (hit) vs
# forced a multi-second rebuild (miss). Exposed via /health.
_hits = 0
_misses = 0

_WORD = re.compile(r"[a-z0-9]+")


class Snapshot:
    """Immutable view of embedded issues (any state) and PRs.

    Holds ALL embedded issues with an ``issue_is_open`` flag: recommendations
    filter to open by default, while search opts into the whole set (so a closed
    tracker is still findable). Embeddings are converted to float32 row-by-row so
    the transient Python lists are dropped as we go.
    """

    def __init__(self, issue_rows, prs: list[PullRequest], pr_rows: list) -> None:
        ids: list[int] = []
        mats: list[np.ndarray] = []
        self.issue_project: list[str | None] = []
        self.issue_tracker: list[str | None] = []
        self.issue_priority: list[str | None] = []
        self.issue_assignee: list[str | None] = []
        self.issue_title_tokens: list[frozenset[str]] = []
        self.issue_pr_refs: list[list[int]] = []
        self.issue_is_open: list[bool] = []
        doc_freq: dict[str, int] = defaultdict(int)  # for IDF over titles
        for (iid, emb, project, tracker, priority, assignee, subject,
                pr_ref_raw, is_open) in issue_rows:
            ids.append(iid)
            mats.append(np.asarray(emb, dtype=np.float32))
            self.issue_project.append(project)
            self.issue_tracker.append(tracker)
            self.issue_priority.append(priority)
            self.issue_assignee.append(assignee)
            toks = frozenset(_WORD.findall((subject or "").lower()))
            self.issue_title_tokens.append(toks)
            for t in toks:
                doc_freq[t] += 1
            if not pr_ref_raw or pr_ref_raw == "[]":
                refs: list[int] = []
            elif isinstance(pr_ref_raw, str):
                refs = json.loads(pr_ref_raw)
            else:
                refs = pr_ref_raw
            self.issue_pr_refs.append(refs)
            self.issue_is_open.append(bool(is_open))
        self.issue_ids: list[int] = ids
        self.issue_mat: np.ndarray = (
            np.asarray(mats, dtype=np.float32) if mats
            else np.zeros((0, 0), dtype=np.float32)
        )
        # IDF for the lexical half of hybrid search: rare title words weigh more
        # than ubiquitous ones ("measure" >> "bluestore"). Unknown query terms
        # get the max weight (idf_default).
        n = max(1, len(ids))
        self.idf: dict[str, float] = {
            t: math.log(n / (1 + df)) + 1.0 for t, df in doc_freq.items()
        }
        self.idf_default: float = math.log(n) + 1.0

        self.pr_ids: list[str] = [p.id for p in prs]
        self.pr_numbers: list[int] = [p.number for p in prs]
        self.pr_mat: np.ndarray = (
            np.asarray([p.embedding for p in prs], dtype=np.float32)
            if prs
            else np.zeros((0, 0), dtype=np.float32)
        )
        self.pr_issue_refs: list[list[int]] = [
            p.referenced_issue_ids or [] for p in prs
        ]

        # Lightweight reference index over ALL PRs (any state, no embeddings) so
        # linked-PR detection is an O(1) lookup instead of a full-table scan.
        # Stored as tuples (cheap to build at 70k+); objects are materialized
        # lazily only for the handful of PRs actually returned. pr_rows rows are
        # (id, number, state, title, url, repo_full_name, refs_json).
        self.pr_meta: dict[str, tuple] = {}
        self.pr_ref_index: dict[int, list[str]] = defaultdict(list)
        self.pr_by_number: dict[int, list[str]] = defaultdict(list)
        for pid, number, state, title, url, repo, refs_raw in pr_rows:
            if not refs_raw or refs_raw == "[]":
                refs: list[int] = []
            elif isinstance(refs_raw, str):
                refs = json.loads(refs_raw)
            else:
                refs = refs_raw
            self.pr_meta[pid] = (number, state, title, url, repo, refs)
            for iid in refs:
                self.pr_ref_index[iid].append(pid)
            if number is not None:
                self.pr_by_number[number].append(pid)

        self.ts = time.time()

    def pr_obj(self, pid: str):
        """Materialize a lightweight PR object from cached metadata."""
        number, state, title, url, repo, refs = self.pr_meta[pid]
        return SimpleNamespace(
            id=pid, number=number, state=state, title=title, url=url,
            repo_full_name=repo, referenced_issue_ids=refs,
        )


def _load(session: Session) -> Snapshot:
    # Load PRs first, then stream issues LAST and consume them immediately -- a
    # streaming (yield_per) cursor and a second query on the same SQLite
    # connection would deadlock the table, so nothing may run between opening the
    # issue cursor and exhausting it.
    prs = list(
        session.scalars(
            select(PullRequest)
            .where(PullRequest.state == "open")
            .where(PullRequest.embedding.is_not(None))
        )
    )
    # Raw metadata for all PRs (fast, no ORM objects, no embedding column).
    pr_rows = session.execute(
        text(
            "SELECT id, number, state, title, url, repo_full_name, "
            "referenced_issue_ids FROM pull_requests"
        )
    ).all()
    # ALL embedded issues (open + closed), as lean column rows streamed into
    # float32 so the whole corpus is searchable without holding 60k+ ORM objects.
    # Column order must match Snapshot.__init__'s unpacking. Consumed here, then
    # the cursor is closed before returning.
    issue_result = session.execute(
        select(
            Issue.id, Issue.embedding, Issue.project_name, Issue.tracker_name,
            Issue.priority, Issue.assignee_login, Issue.subject,
            Issue.referenced_pr_numbers, Issue.is_open,
        ).where(Issue.embedding.is_not(None))
    )
    try:
        return Snapshot(issue_result.yield_per(2000), prs, pr_rows)
    finally:
        issue_result.close()


def get_snapshot(session: Session) -> Snapshot:
    """Return the cached snapshot, rebuilding if invalidated or stale."""
    global _snapshot, _hits, _misses
    with _LOCK:
        if _snapshot is None or (time.time() - _snapshot.ts) > _TTL_SECONDS:
            _misses += 1
            _snapshot = _load(session)
        else:
            _hits += 1
        return _snapshot


def invalidate() -> None:
    """Drop the cache so the next request rebuilds it (call after embedding changes)."""
    global _snapshot
    with _LOCK:
        _snapshot = None


def cache_stats() -> dict[str, object]:
    """Snapshot-cache hits/misses and whether a warm snapshot is loaded."""
    with _LOCK:
        warm = _snapshot is not None
        age = round(time.time() - _snapshot.ts, 1) if _snapshot else None
    return {"hits": _hits, "misses": _misses, "warm": warm, "age_seconds": age}
