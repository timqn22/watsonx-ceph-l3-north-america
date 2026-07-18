"""Personalized task recommendations (Feature B).

Given a free-text description of someone's skills, rank open issues by fit using
the *same* Granite embedder as the linkage feature -- so this needs no extra
model and no watsonx quota. Cosine similarity between the skill-prompt embedding
and each issue embedding drives a 0-100 fit score, with optional filters and a
couple of "stretch" picks to encourage growth.

A natural-language rationale per issue (via a Granite *instruct* model) is a
documented future upgrade; here we surface an honest keyword-overlap "why".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.embedder import Embedder, get_embedder
from ..ai.index_cache import get_snapshot
from ..ai.reranker import Reranker, get_reranker
from ..ai.scoring import components_for
from ..config import get_settings
from ..models import Issue, UserProfile
from ..text import content_hash, issue_embed_text

_TOKEN_RE = re.compile(r"[a-z][a-z0-9+-]{2,}")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "are",
    "was", "will", "not", "but", "you", "your", "our", "can", "all", "any",
    "some", "new", "use", "used", "using", "issue", "issues", "bug", "fix",
    "fixed", "when", "then", "into", "out", "get", "set", "how", "why", "what",
    "know", "good", "well", "comfortable", "familiar", "experience", "level",
}

# Fit-score band (0-100) from which "stretch" growth picks are drawn.
_STRETCH_LOW = 55
_STRETCH_HIGH = 80


@dataclass
class Recommendation:
    issue_id: int
    fit_score: int
    similarity: float
    reason: str
    is_stretch: bool


def _salient_tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP}


def _reason(skill_prompt: str, issue: Issue) -> str:
    """Honest keyword-overlap explanation (no LLM)."""
    skills = _salient_tokens(skill_prompt)
    issue_txt = _salient_tokens(f"{issue.subject} {issue.description or ''}")
    shared = sorted(skills & issue_txt, key=len, reverse=True)[:4]
    if shared:
        return "Overlaps on " + ", ".join(shared)
    return "Strong semantic match"


_TRACKER_RE = re.compile(r"\b(\d{4,7})\b")
_QUERY_STOP_RE = re.compile(
    r"(?i)\b(tracker|trackers|issue|issues|like|similar|find|show|me|something|"
    r"anything|on|about|for|the|number|no)\b|#"
)


def resolve_query_vector(
    session: Session, query: str, embedder: Embedder
) -> tuple[np.ndarray | None, set[int], str]:
    """Turn a free-text/tracker query into a single unit query vector.

    Handles three shapes, and any mix of them:
      * "like tracker 77219"          -> that issue's own embedding
      * "performance counters bluestore" -> the text's embedding
      * both                          -> the (renormalized) mean of the two
    Returns (vector, tracker_ids_to_exclude, text_for_reason). The referenced
    trackers are excluded from results so a "like #77219" search never returns
    #77219 itself.
    """
    vectors: list[np.ndarray] = []
    exclude: set[int] = set()
    for tok in _TRACKER_RE.findall(query):
        issue = session.get(Issue, int(tok))
        if issue is not None and issue.embedding is not None:
            vectors.append(np.asarray(issue.embedding, dtype=np.float32))
            exclude.add(int(tok))

    free_text = _QUERY_STOP_RE.sub(" ", _TRACKER_RE.sub(" ", query)).strip()
    text_for_reason = ""
    if _salient_tokens(free_text):
        vectors.append(np.asarray(embedder.embed_texts([free_text])[0], dtype=np.float32))
        text_for_reason = free_text
    if not vectors:  # nothing parseable -> embed the raw query
        vectors.append(np.asarray(embedder.embed_texts([query])[0], dtype=np.float32))
        text_for_reason = query

    v = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(v))
    if norm:
        v = v / norm
    return v.astype(np.float32), exclude, text_for_reason


def ensure_skill_embedding(profile: UserProfile, embedder: Embedder) -> None:
    """(Re)embed the profile's skill prompt only when it has changed."""
    h = content_hash(profile.skill_prompt)
    if profile.skill_embedding is None or profile.skill_embedded_hash != h:
        profile.skill_embedding = embedder.embed_texts([profile.skill_prompt])[0]
        profile.skill_embedded_hash = h


def recommend_issues(
    session: Session,
    *,
    skill_prompt: str,
    projects: list[str] | None = None,
    trackers: list[str] | None = None,
    priorities: list[str] | None = None,
    limit: int = 15,
    stretch: int = 2,
    exclude_issue_ids: set[int] | None = None,
    exclude_assigned: bool = True,
    affinity_components: set[str] | None = None,
    affinity_weight: float = 0.0,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    query_vector: np.ndarray | None = None,
    lexical_weight: float = 0.0,
    include_closed: bool = False,
    exclude_linked: bool = False,
) -> list[Recommendation]:
    """Rank open issues by fit to ``skill_prompt``, applying optional filters.

    Returns up to ``limit`` picks: the strongest matches, plus up to ``stretch``
    "growth" issues drawn from a mid fit band (marked ``is_stretch``).
    ``exclude_issue_ids`` drops issues already being worked on, and
    ``exclude_assigned`` drops issues that already have an assignee -- so we only
    ever recommend genuinely available, unclaimed work.

    ``query_vector`` (search mode) supplies a precomputed unit query vector to
    rank by instead of embedding ``skill_prompt``; ``skill_prompt`` is then used
    only for the keyword-overlap reason string.
    """
    embedder = embedder or get_embedder()
    if query_vector is not None:
        skill_vec = np.asarray(query_vector, dtype=np.float32)
    else:
        if not skill_prompt.strip():
            return []
        skill_vec = np.asarray(embedder.embed_texts([skill_prompt])[0], dtype=np.float32)

    # Filter candidates against the cached embedding snapshot (no per-request
    # reload of every vector from SQLite).
    snap = get_snapshot(session)
    if not snap.issue_ids:
        return []
    proj_set = set(projects) if projects else None
    trk_set = set(trackers) if trackers else None
    pri_set = set(priorities) if priorities else None
    excl = exclude_issue_ids or set()

    idxs: list[int] = []
    for k, iid in enumerate(snap.issue_ids):
        if not include_closed and not snap.issue_is_open[k]:
            continue  # recommendations are open work; search opts into all
        if exclude_assigned and snap.issue_assignee[k]:
            continue
        if exclude_linked and (
            snap.pr_ref_index.get(iid)
            or any(snap.pr_by_number.get(n) for n in snap.issue_pr_refs[k])
        ):
            continue  # a PR already references this tracker (either direction)
        if iid in excl:
            continue
        if proj_set is not None and snap.issue_project[k] not in proj_set:
            continue
        if trk_set is not None and snap.issue_tracker[k] not in trk_set:
            continue
        if pri_set is not None and snap.issue_priority[k] not in pri_set:
            continue
        idxs.append(k)
    if not idxs:
        return []

    sub = snap.issue_mat[idxs]  # (m, d)
    sims = sub @ skill_vec  # unit-length vectors -> dot == cosine
    # Hybrid search: add a lexical (title keyword-overlap) score so an issue that
    # literally contains the query words isn't buried by dense similarity. The
    # overlap is IDF-weighted -- matching a rare, distinctive query word
    # ("measure") counts far more than a ubiquitous one ("bluestore").
    if lexical_weight and skill_prompt.strip():
        q_tokens = _salient_tokens(skill_prompt)
        if q_tokens:
            idf = getattr(snap, "idf", {})
            idf_default = getattr(snap, "idf_default", 1.0)
            weights = {t: idf.get(t, idf_default) for t in q_tokens}
            denom = sum(weights.values()) or 1.0
            lex = np.array(
                [
                    sum(weights[t] for t in (q_tokens & snap.issue_title_tokens[k]))
                    / denom
                    for k in idxs
                ],
                dtype=np.float32,
            )
            sims = sims + lexical_weight * lex
    # Component affinity: nudge issues in the user's historical subsystems up.
    if affinity_components and affinity_weight:
        boosts = np.array(
            [
                affinity_weight
                if components_for(snap.issue_project[k]) & affinity_components
                else 0.0
                for k in idxs
            ],
            dtype=np.float32,
        )
        sims = sims + boosts
    order = np.argsort(-sims)
    ranked = [(snap.issue_ids[idxs[o]], float(sims[o])) for o in order]

    # FIT is shown relative to the best available match: the strongest issue
    # reads high and weaker ones taper, which is far more intuitive than a bare
    # Granite cosine (~0.3-0.5) rendered as a tiny "30% fit". Raw cosine is kept
    # as `similarity`. `_fit(sim)` maps the top candidate to ~100 and scales down.
    top_sim = ranked[0][1] if ranked else 0.0

    def _fit(sim: float) -> int:
        if top_sim <= 0:
            return 0
        return int(np.clip(round(100.0 * max(0.0, sim) / top_sim), 0, 100))

    # Precision stage: if a cross-encoder is enabled, re-rank the top embedding
    # candidates by reading the skill text against each issue. Fit then reflects
    # the cross-encoder relevance; extras beyond `limit` become stretch picks.
    reranker = reranker or get_reranker()
    if reranker.enabled and ranked:
        pool = ranked[: get_settings().rerank_top_k]
        rows = [(iid, sim, session.get(Issue, iid)) for iid, sim in pool]
        rr = reranker.scores(
            skill_prompt,
            [issue_embed_text(r.subject, r.description) if r else "" for _, _, r in rows],
        )
        # Show fit relative to the best reranked match, exactly like the non-rerank
        # path -- otherwise a domain-mismatched cross-encoder (relevance ~0.02)
        # renders every pick as "0 fit". Top pick reads ~100 and tapers down.
        rr_top = max(rr) if rr else 0.0

        def _rr_fit(x: float) -> int:
            return int(np.clip(round(100.0 * x / rr_top), 0, 100)) if rr_top > 0 else 0

        out: list[Recommendation] = []
        for pos, i in enumerate(sorted(range(len(rows)), key=lambda i: -rr[i])):
            if len(out) >= limit + stretch:
                break
            iid, sim, issue = rows[i]
            out.append(
                Recommendation(
                    issue_id=iid,
                    fit_score=_rr_fit(rr[i]),
                    similarity=sim,
                    reason=_reason(skill_prompt, issue) if issue else "",
                    is_stretch=pos >= limit,
                )
            )
        return out

    # Top `limit` are the strong picks; stretch picks are a bonus from a mid
    # fit band below the cut, so `limit` always returns that many primaries.
    primary = ranked[:limit]
    chosen = {iid for iid, _ in primary}
    stretch_sel: list[tuple[int, float]] = []
    for iid, sim in ranked[limit:]:
        if len(stretch_sel) >= stretch:
            break
        if _STRETCH_LOW <= _fit(sim) < _STRETCH_HIGH and iid not in chosen:
            stretch_sel.append((iid, sim))

    selected = [(iid, sim, False) for iid, sim in primary]
    selected += [(iid, sim, True) for iid, sim in stretch_sel]

    # Fetch only the selected rows (small) to build the keyword-overlap reason.
    out: list[Recommendation] = []
    for iid, sim, is_stretch in selected:
        issue = session.get(Issue, iid)
        out.append(
            Recommendation(
                issue_id=iid,
                fit_score=_fit(sim),
                similarity=sim,
                reason=_reason(skill_prompt, issue) if issue else "",
                is_stretch=is_stretch,
            )
        )
    return out


def get_or_create_profile(session: Session, external_id: str = "me") -> UserProfile:
    profile = session.scalar(
        select(UserProfile).where(UserProfile.external_id == external_id)
    )
    if profile is None:
        profile = UserProfile(external_id=external_id, skill_prompt="")
        session.add(profile)
        session.commit()
    return profile
