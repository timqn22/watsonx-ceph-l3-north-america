"""PR <-> tracker linkage matching.

The flagship feature: given embedded PRs and issues, find likely-but-missing
links. A PR whose body already references an existing issue via ``#123`` is
treated as already linked and skipped as a *source* of suggestions.

Similarity is cosine over the stored unit vectors, computed with numpy. At
hackathon scale (thousands of items) a full matrix multiply is instant and far
simpler than a vector database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Issue, LinkSuggestion, PullRequest

logger = logging.getLogger(__name__)


@dataclass
class Match:
    issue_id: int
    similarity: float


def _matrix(rows: list) -> np.ndarray:
    """Stack row.embedding vectors into a 2D array (rows without embeddings excluded upstream)."""
    return np.asarray([r.embedding for r in rows], dtype=np.float32)


def _top_matches(
    pr_vec: np.ndarray,
    issues: list[Issue],
    issue_mat: np.ndarray,
    *,
    min_similarity: float,
    limit: int,
) -> list[Match]:
    if issue_mat.size == 0:
        return []
    # Vectors are pre-normalized, so dot product == cosine similarity.
    sims = issue_mat @ pr_vec
    order = np.argsort(-sims)[:limit]
    return [
        Match(issue_id=issues[i].id, similarity=float(sims[i]))
        for i in order
        if sims[i] >= min_similarity
    ]


def _load_embedded_issues(session: Session, *, open_only: bool = True) -> list[Issue]:
    stmt = select(Issue).where(Issue.embedding.is_not(None))
    if open_only:
        stmt = stmt.where(Issue.is_open.is_(True))
    return list(session.scalars(stmt))


def suggest_links_for_pr(
    session: Session,
    pr: PullRequest,
    *,
    min_similarity: float,
    limit: int = 5,
    candidate_issues: list[Issue] | None = None,
) -> list[Match]:
    """Top issue matches for one PR, above the similarity threshold.

    If the PR already references an existing issue, returns no suggestions --
    it is considered linked.
    """
    if pr.embedding is None:
        return []
    if candidate_issues is None:
        candidate_issues = _load_embedded_issues(session, open_only=True)
    if not candidate_issues:
        return []

    existing_ids = {i.id for i in candidate_issues}
    if pr.referenced_issue_ids and existing_ids.intersection(pr.referenced_issue_ids):
        return []  # already linked to a known issue

    pr_vec = np.asarray(pr.embedding, dtype=np.float32)
    issue_mat = _matrix(candidate_issues)
    return _top_matches(
        pr_vec,
        candidate_issues,
        issue_mat,
        min_similarity=min_similarity,
        limit=limit,
    )


def rebuild_suggestions(
    session: Session,
    *,
    min_similarity: float,
    per_pr_limit: int = 3,
) -> int:
    """Recompute the link_suggestions cache for all open, unlinked PRs.

    Preserves any human decisions (accepted/rejected/ignored); only refreshes
    still-pending rows and inserts new candidates. Returns the number of
    pending suggestions after the run.
    """
    issues = _load_embedded_issues(session, open_only=True)
    if not issues:
        logger.info("rebuild_suggestions: no embedded issues yet")
        return 0
    issue_mat = _matrix(issues)

    prs = list(
        session.scalars(
            select(PullRequest)
            .where(PullRequest.embedding.is_not(None))
            .where(PullRequest.state == "open")
        )
    )

    # Decisions we must not clobber, keyed by (pr_id, issue_id).
    decided: dict[tuple[str, int], LinkSuggestion] = {
        (s.pr_id, s.issue_id): s
        for s in session.scalars(
            select(LinkSuggestion).where(LinkSuggestion.status != "pending")
        )
    }

    # Drop stale pending rows; we'll regenerate them fresh.
    for s in session.scalars(
        select(LinkSuggestion).where(LinkSuggestion.status == "pending")
    ):
        session.delete(s)
    session.flush()

    existing_ids = {i.id for i in issues}
    pending = 0
    for pr in prs:
        if pr.referenced_issue_ids and existing_ids.intersection(
            pr.referenced_issue_ids
        ):
            continue
        pr_vec = np.asarray(pr.embedding, dtype=np.float32)
        for m in _top_matches(
            pr_vec, issues, issue_mat, min_similarity=min_similarity, limit=per_pr_limit
        ):
            if (pr.id, m.issue_id) in decided:
                continue  # human already ruled on this pair
            session.add(
                LinkSuggestion(
                    pr_id=pr.id,
                    issue_id=m.issue_id,
                    similarity=m.similarity,
                    model_id=None,
                    status="pending",
                )
            )
            pending += 1

    session.commit()
    logger.info("rebuild_suggestions: %s pending suggestions", pending)
    return pending
