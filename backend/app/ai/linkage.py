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

from ..config import get_settings
from ..models import Issue, LinkSuggestion, PullRequest
from ..text import issue_embed_text, pr_embed_text
from .index_cache import get_snapshot
from .reranker import Reranker, get_reranker
from .scoring import get_weights, structural_bonus

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


@dataclass
class RelatedPR:
    pr: PullRequest
    relationship: str  # "linked" | "suggested"
    similarity: float | None
    confidence: float | None  # calibrated 0..1 for display
    # For linked PRs: which side records the link.
    #   "pr"      -> PR body references the tracker
    #   "tracker" -> tracker references the PR, but the PR does NOT link back
    #   "both"    -> both sides agree
    link_direction: str | None = None
    # For two-hop suggestions: the similar tracker whose recorded link led here.
    via_issue_id: int | None = None
    via_issue_subject: str | None = None


def calibrate(cosine: float, floor: float) -> float:
    """Rescale raw cosine to a 0..1 confidence, subtracting the domain baseline.

    Granite similarities among Ceph items sit well above zero even when
    unrelated, so a raw 0.77 is not "77% related". Mapping [floor..1] -> [0..1]
    makes the number honest: at or below the floor reads as ~0%.
    """
    if cosine <= floor:
        return 0.0
    return min(1.0, (cosine - floor) / (1.0 - floor))


def related_prs_for_issue(
    session: Session,
    issue: Issue,
    *,
    limit: int | None = None,
    min_similarity: float | None = None,
    floor: float | None = None,
    extra_pr_numbers: set[int] | None = None,
    reranker: Reranker | None = None,
) -> list[RelatedPR]:
    """PRs related to an issue, for the issue-page panel.

    If any PR is already linked (from either side), shows ONLY those linked PRs
    -- a recorded link is the answer, so no speculative matches alongside it.
    Otherwise shows the strongest ``limit`` possible matches above the bar.
    Includes PRs in any state (open/merged/closed).
    """
    settings = get_settings()
    limit = settings.related_pr_limit if limit is None else limit
    if min_similarity is None:
        min_similarity = settings.related_pr_min_similarity
    if floor is None:
        floor = settings.similarity_floor

    snap = get_snapshot(session)

    # 1) Definite links win outright -- detected from EITHER side (the PR
    #    referencing the issue, or the tracker referencing the PR, incl. any
    #    PR numbers the caller found in the issue's comments). O(1) lookups
    #    against the cached reference index -- no full-table scan.
    tracker_pr_nums = set(issue.referenced_pr_numbers or []) | (extra_pr_numbers or set())
    dirs: dict[str, str] = {}
    for pid in snap.pr_ref_index.get(issue.id, []):
        dirs[pid] = "pr"
    for num in tracker_pr_nums:
        for pid in snap.pr_by_number.get(num, []):
            dirs[pid] = "both" if pid in dirs else "tracker"
    if dirs:
        linked = [
            RelatedPR(snap.pr_obj(pid), "linked", None, None, direction)
            for pid, direction in dirs.items()
        ]
        # Tracker-only links (PR hasn't back-referenced) surface first as they're
        # the actionable ones.
        linked.sort(key=lambda r: r.link_direction != "tracker")
        return linked[:limit]

    # 2) Nothing linked -> blend two retrieval paths, best confidence first:
    #    * two-hop: PRs *recorded as linked* to highly similar trackers. The
    #      issue<->issue hop is the strong signal (~70% top-1 vs the much harder
    #      direct issue->PR jump), and the second hop is a known-true link -- so
    #      these are typically the most trustworthy suggestions.
    #    * direct: the strongest issue->PR content matches, for fixes whose
    #      tracker sibling doesn't exist.
    via = _via_similar_tracker_prs(session, issue, snap, limit=limit, floor=floor)
    direct = _suggested_prs(
        session,
        issue,
        snap,
        limit=limit,
        min_similarity=min_similarity,
        floor=floor,
        reranker=reranker,
        exclude_numbers=set(),
    )
    best: dict[str, RelatedPR] = {}
    for r in via + direct:  # via first so it wins confidence ties
        cur = best.get(r.pr.id)
        if cur is None or (r.confidence or 0) > (cur.confidence or 0):
            best[r.pr.id] = r
    merged = sorted(best.values(), key=lambda r: -(r.confidence or 0))
    return merged[:limit]


@dataclass
class SimilarTracker:
    issue: Issue
    similarity: float
    confidence: float  # calibrated 0..1


def similar_trackers_for_issue(
    session: Session,
    issue: Issue,
    *,
    limit: int | None = None,
    min_similarity: float | None = None,
    floor: float | None = None,
) -> list[SimilarTracker]:
    """Trackers highly similar to this one -- the possible-duplicate warning.

    Pure issue<->issue similarity (the matcher's strongest signal) with a high
    precision bar. Closed trackers are included on purpose: reporting a bug that
    was already fixed is the most common duplicate case.
    """
    settings = get_settings()
    limit = settings.duplicate_limit if limit is None else limit
    if min_similarity is None:
        min_similarity = settings.duplicate_min_similarity
    if floor is None:
        floor = settings.similarity_floor

    snap = get_snapshot(session)
    if issue.embedding is None or not snap.issue_ids:
        return []
    vec = np.asarray(issue.embedding, dtype=np.float32)
    sims = snap.issue_mat @ vec
    order = np.argsort(-sims)[: limit + 8]

    out: list[SimilarTracker] = []
    for idx in order:
        k = int(idx)
        iid = snap.issue_ids[k]
        if iid == issue.id:
            continue
        sim = float(sims[k])
        if sim < min_similarity or len(out) >= limit:
            break
        other = session.get(Issue, iid)
        if other is None:
            continue
        out.append(SimilarTracker(other, sim, calibrate(sim, floor)))
    return out


def _via_similar_tracker_prs(
    session: Session,
    issue: Issue,
    snap,
    *,
    limit: int,
    floor: float,
) -> list[RelatedPR]:
    """PRs linked to trackers highly similar to this one (two-hop retrieval).

    Confidence is the calibrated issue<->issue similarity of the tracker the
    link came from -- honest, since that hop is what the suggestion rests on.
    Closed siblings are included on purpose: a closed similar tracker's merged
    PR is exactly the "how was this solved before" pointer a reader wants.
    """
    if issue.embedding is None or not snap.issue_ids:
        return []
    settings = get_settings()
    vec = np.asarray(issue.embedding, dtype=np.float32)
    sims = snap.issue_mat @ vec
    order = np.argsort(-sims)[: limit * 8]

    out: list[RelatedPR] = []
    seen: set[str] = set()
    for idx in order:
        k = int(idx)
        iid = snap.issue_ids[k]
        if iid == issue.id:
            continue
        sim = float(sims[k])
        if sim < settings.related_via_issue_min_similarity or len(out) >= limit:
            break
        # Linked PRs of the similar tracker, from either link direction.
        pids = list(snap.pr_ref_index.get(iid, []))
        for num in snap.issue_pr_refs[k]:
            pids.extend(snap.pr_by_number.get(num, []))
        if not pids:
            continue
        via = session.get(Issue, iid)
        subject = via.subject if via is not None else None
        for pid in pids:
            if pid in seen or len(out) >= limit:
                continue
            seen.add(pid)
            out.append(
                RelatedPR(
                    snap.pr_obj(pid),
                    "suggested",
                    sim,
                    calibrate(sim, floor),
                    via_issue_id=iid,
                    via_issue_subject=subject,
                )
            )
    return out


def _suggested_prs(
    session: Session,
    issue: Issue,
    snap,
    *,
    limit: int,
    min_similarity: float,
    floor: float,
    reranker: Reranker | None,
    exclude_numbers: set[int],
) -> list[RelatedPR]:
    """Strongest possible-match PRs for an issue (excluding already-linked ones).

    Takes the top cosine candidates from the cached open-PR snapshot, re-ranks
    with the hybrid score (content + component/branch structure), and returns
    those above the bar with a calibrated confidence. If a cross-encoder is
    enabled it re-orders the top pool instead (confidence then reflects the
    cross-encoder's relevance).
    """
    if issue.embedding is None or not snap.pr_ids:
        return []
    settings = get_settings()
    weights = get_weights()
    vec = np.asarray(issue.embedding, dtype=np.float32)
    sims = snap.pr_mat @ vec

    candidates = np.argsort(-sims)[: max(limit * 8, settings.rerank_top_k)]
    scored: list[tuple[float, float, PullRequest]] = []
    for idx in candidates:
        pr = session.get(PullRequest, snap.pr_ids[int(idx)])
        if pr is None or pr.number in exclude_numbers:
            continue
        cos = float(sims[idx])
        scored.append((cos + structural_bonus(pr, issue, weights), cos, pr))
    scored.sort(key=lambda t: -t[0])

    reranker = reranker or get_reranker()
    pool = scored[: settings.rerank_top_k]
    if reranker.enabled and pool:
        q = issue_embed_text(issue.subject, issue.description)
        rr = reranker.scores(q, [pr_embed_text(pr.title, pr.body) for _, _, pr in pool])
        ordered = sorted(range(len(pool)), key=lambda i: -rr[i])
        out: list[RelatedPR] = []
        for i in ordered:
            if rr[i] < settings.rerank_min_score or len(out) >= limit:
                break
            _, cos, pr = pool[i]
            out.append(RelatedPR(pr, "suggested", cos, rr[i]))
        return out

    out = []
    for hybrid, cos, pr in scored:
        if hybrid < min_similarity or len(out) >= limit:
            break
        out.append(RelatedPR(pr, "suggested", cos, calibrate(hybrid, floor)))
    return out


def rebuild_suggestions(
    session: Session,
    *,
    min_similarity: float,
    per_pr_limit: int = 3,
    model_id: str | None = None,
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
    weights = get_weights()
    pending = 0
    for pr in prs:
        if pr.referenced_issue_ids and existing_ids.intersection(
            pr.referenced_issue_ids
        ):
            continue
        pr_vec = np.asarray(pr.embedding, dtype=np.float32)
        sims = issue_mat @ pr_vec
        # Take the top cosine candidates, then re-rank with the hybrid score.
        cand = np.argsort(-sims)[: max(per_pr_limit * 8, 25)]
        scored = sorted(
            (
                (float(sims[i]) + structural_bonus(pr, issues[i], weights), issues[i])
                for i in cand
            ),
            key=lambda t: -t[0],
        )
        count = 0
        for hybrid, issue in scored:
            if hybrid < min_similarity or count >= per_pr_limit:
                break
            if (pr.id, issue.id) in decided:
                continue  # human already ruled on this pair
            session.add(
                LinkSuggestion(
                    pr_id=pr.id,
                    issue_id=issue.id,
                    similarity=hybrid,
                    model_id=model_id,
                    status="pending",
                )
            )
            pending += 1
            count += 1

    session.commit()
    logger.info("rebuild_suggestions: %s pending suggestions", pending)
    return pending
