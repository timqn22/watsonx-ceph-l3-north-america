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

from ..config import get_settings
from ..models import Issue, PullRequest


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

    open_issue_ids = set(
        session.scalars(select(Issue.id).where(Issue.is_open.is_(True)))
    )
    open_prs = list(
        session.scalars(
            select(PullRequest).where(PullRequest.state == "open")
        )
    )

    evidence: dict[int, WorkEvidence] = {}

    # 1) Definite: PR body references the issue.
    for pr in open_prs:
        for iid in pr.referenced_issue_ids or []:
            if iid in open_issue_ids and iid not in evidence:
                evidence[iid] = WorkEvidence("referenced", pr, None)

    # 2) Likely: strong embedding similarity (only for issues not already
    #    referenced, and only using embedded rows).
    issues = list(
        session.scalars(
            select(Issue)
            .where(Issue.is_open.is_(True))
            .where(Issue.embedding.is_not(None))
        )
    )
    prs = [p for p in open_prs if p.embedding is not None]
    if issues and prs:
        issue_mat = np.asarray([i.embedding for i in issues], dtype=np.float32)
        pr_mat = np.asarray([p.embedding for p in prs], dtype=np.float32)
        sims = issue_mat @ pr_mat.T  # unit vectors -> cosine
        best_pr = np.argmax(sims, axis=1)
        best_val = sims[np.arange(len(issues)), best_pr]
        for row, issue in enumerate(issues):
            if issue.id in evidence:
                continue
            score = float(best_val[row])
            if score >= min_similarity:
                evidence[issue.id] = WorkEvidence("match", prs[best_pr[row]], score)

    return evidence


def in_progress_issue_ids(
    session: Session, *, min_similarity: float | None = None
) -> set[int]:
    """Just the set of open-issue ids that already have work in flight."""
    return set(in_progress_map(session, min_similarity=min_similarity).keys())
