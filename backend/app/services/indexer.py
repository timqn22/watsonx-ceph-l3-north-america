"""Embedding indexer.

Finds issues/PRs whose embedding is missing or stale (content changed since it
was last embedded) and (re)embeds them in batches with the configured embedder
-- Granite via watsonx when available. Writes the vector and records the hash it
was embedded at, so unchanged rows are never re-embedded.
"""

from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..ai.embedder import Embedder, get_embedder
from ..models import Issue, PullRequest
from ..text import issue_embed_text, pr_embed_text

logger = logging.getLogger(__name__)

BATCH = 32


def _needs_embedding(model):
    return or_(
        model.embedding.is_(None),
        model.embedded_hash.is_(None),
        model.embedded_hash != model.content_hash,
    )


def refresh_embeddings(session: Session, embedder: Embedder | None = None) -> int:
    """Embed all stale issues and PRs. Returns number of rows embedded."""
    embedder = embedder or get_embedder()
    total = 0

    stale_issues = list(session.scalars(select(Issue).where(_needs_embedding(Issue))))
    for i in range(0, len(stale_issues), BATCH):
        batch = stale_issues[i : i + BATCH]
        vectors = embedder.embed_texts(
            [issue_embed_text(x.subject, x.description) for x in batch]
        )
        for row, vec in zip(batch, vectors):
            row.embedding = vec
            row.embedded_hash = row.content_hash
        total += len(batch)

    stale_prs = list(
        session.scalars(select(PullRequest).where(_needs_embedding(PullRequest)))
    )
    for i in range(0, len(stale_prs), BATCH):
        batch = stale_prs[i : i + BATCH]
        vectors = embedder.embed_texts([pr_embed_text(x.title, x.body) for x in batch])
        for row, vec in zip(batch, vectors):
            row.embedding = vec
            row.embedded_hash = row.content_hash
        total += len(batch)

    session.commit()
    if total:
        logger.info("refresh_embeddings: embedded %s rows via %s", total, embedder.model_id)
    return total
