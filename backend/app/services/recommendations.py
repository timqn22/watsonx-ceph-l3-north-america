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
from ..models import Issue, UserProfile
from ..text import content_hash

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
    return "Semantically close to your described skills"


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
    embedder: Embedder | None = None,
) -> list[Recommendation]:
    """Rank open issues by fit to ``skill_prompt``, applying optional filters.

    Returns up to ``limit`` picks: the strongest matches, plus up to ``stretch``
    "growth" issues drawn from a mid fit band (marked ``is_stretch``).
    """
    embedder = embedder or get_embedder()
    if not skill_prompt.strip():
        return []
    skill_vec = np.asarray(embedder.embed_texts([skill_prompt])[0], dtype=np.float32)

    stmt = select(Issue).where(Issue.is_open.is_(True)).where(
        Issue.embedding.is_not(None)
    )
    if projects:
        stmt = stmt.where(Issue.project_name.in_(projects))
    if trackers:
        stmt = stmt.where(Issue.tracker_name.in_(trackers))
    if priorities:
        stmt = stmt.where(Issue.priority.in_(priorities))

    candidates = list(session.scalars(stmt))
    if not candidates:
        return []

    mat = np.asarray([c.embedding for c in candidates], dtype=np.float32)
    sims = mat @ skill_vec  # vectors are unit-length -> dot == cosine
    order = np.argsort(-sims)

    ranked: list[Recommendation] = []
    for idx in order:
        issue = candidates[idx]
        sim = float(sims[idx])
        ranked.append(
            Recommendation(
                issue_id=issue.id,
                fit_score=int(round(max(0.0, sim) * 100)),
                similarity=sim,
                reason=_reason(skill_prompt, issue),
                is_stretch=False,
            )
        )

    # Top `limit` are the strong picks; stretch picks are a bonus drawn from a
    # mid fit band below the cut, so `limit` always returns that many primaries.
    primary = ranked[:limit]
    chosen_ids = {r.issue_id for r in primary}

    stretch_picks: list[Recommendation] = []
    for r in ranked[limit:]:
        if len(stretch_picks) >= stretch:
            break
        if _STRETCH_LOW <= r.fit_score < _STRETCH_HIGH and r.issue_id not in chosen_ids:
            r.is_stretch = True
            stretch_picks.append(r)

    return primary + stretch_picks


def get_or_create_profile(session: Session, external_id: str = "me") -> UserProfile:
    profile = session.scalar(
        select(UserProfile).where(UserProfile.external_id == external_id)
    )
    if profile is None:
        profile = UserProfile(external_id=external_id, skill_prompt="")
        session.add(profile)
        session.commit()
    return profile
