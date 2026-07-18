"""Detect which open issues are already being worked on by a pull request.

Two signals, strongest first:
  * "referenced" -- an open PR's body links the issue (``#123`` or a tracker
    URL). Definite: someone is on it.
  * "match"      -- an open PR's Granite embedding is highly similar to the
    issue, above ``in_progress_min_similarity``. Likely: someone is on it but
    never linked the tracker.

This powers two things: a manager view of *unassigned* issues that already have
work in flight (people who started without assigning themselves), and an
exclusion set so the recommender never suggests work that's already taken.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.index_cache import get_snapshot
from ..config import get_settings
from ..models import PullRequest


@dataclass
class WorkEvidence:
    kind: str  # "referenced" | "match"
    pr: PullRequest
    similarity: float | None  # None for referenced links


def in_progress_map(
    session: Session, *, min_similarity: float | None = None
) -> dict[int, WorkEvidence]:
    """Map open-issue id -> evidence that an open PR is already working on it.

    Reference links win over similarity matches. Only open PRs count as "in
    flight" (a merged PR means the work already landed).
    """
    if min_similarity is None:
        min_similarity = get_settings().in_progress_min_similarity

    snap = get_snapshot(session)
    # The snapshot now holds all issues; "in progress" only concerns open ones.
    open_issue_ids = {
        iid for iid, is_open in zip(snap.issue_ids, snap.issue_is_open) if is_open
    }

    # PR objects are needed as evidence; fetch the open ones once (cheap vs the
    # embedding matrices, which come from the cached snapshot).
    open_prs = list(
        session.scalars(select(PullRequest).where(PullRequest.state == "open"))
    )
    pr_by_id = {p.id: p for p in open_prs}

    evidence: dict[int, WorkEvidence] = {}

    # 1) Definite: a PR body references the issue.
    for pr in open_prs:
        for iid in pr.referenced_issue_ids or []:
            if iid in open_issue_ids and iid not in evidence:
                evidence[iid] = WorkEvidence("referenced", pr, None)

    # 2) Likely: strong embedding similarity (issues not already referenced).
    #    The snapshot holds all issues; only open ones can be "in progress", so
    #    matmul just those rows (keeps this off the closed-issue count).
    open_rows = [k for k, op in enumerate(snap.issue_is_open) if op]
    if open_rows and snap.pr_mat.size:
        open_mat = snap.issue_mat[open_rows]
        sims = open_mat @ snap.pr_mat.T  # unit vectors -> cosine
        best_pr = np.argmax(sims, axis=1)
        best_val = sims[np.arange(len(open_rows)), best_pr]
        for i, row in enumerate(open_rows):
            issue_id = snap.issue_ids[row]
            if issue_id in evidence:
                continue
            score = float(best_val[i])
            if score >= min_similarity:
                pr = pr_by_id.get(snap.pr_ids[int(best_pr[i])])
                if pr is not None:
                    evidence[issue_id] = WorkEvidence("match", pr, score)

    return evidence


def in_progress_issue_ids(
    session: Session, *, min_similarity: float | None = None
) -> set[int]:
    """Just the set of open-issue ids that already have work in flight."""
    return set(in_progress_map(session, min_similarity=min_similarity).keys())
