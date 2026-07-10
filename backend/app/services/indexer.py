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


def _embed_rows(session, embedder, rows, text_fn, label: str) -> int:
    """Embed a list of rows in batches, logging progress and committing as we go.

    Periodic commits mean a huge run keeps partial progress (and the delta logic
    resumes from where it stopped) even if interrupted.
    """
    n = len(rows)
    if n:
        logger.info("refresh_embeddings: %s %s rows to embed", n, label)
    for i in range(0, n, BATCH):
        batch = rows[i : i + BATCH]
        vectors = embedder.embed_texts([text_fn(x) for x in batch])
        for row, vec in zip(batch, vectors):
            row.embedding = vec
            row.embedded_hash = row.content_hash
        done = min(i + BATCH, n)
        # Commit + log every ~20 batches so long runs are durable and visible.
        if (i // BATCH) % 20 == 0 or done == n:
            session.commit()
            if n > BATCH:
                logger.info("refresh_embeddings: %s %s/%s embedded", label, done, n)
    return n


def refresh_embeddings(session: Session, embedder: Embedder | None = None) -> int:
    """Embed all stale issues and PRs. Returns number of rows embedded."""
    embedder = embedder or get_embedder()

    stale_issues = list(session.scalars(select(Issue).where(_needs_embedding(Issue))))
    stale_prs = list(
        session.scalars(select(PullRequest).where(_needs_embedding(PullRequest)))
    )
    total = _embed_rows(
        session, embedder, stale_issues,
        lambda x: issue_embed_text(x.subject, x.description), "issues",
    )
    total += _embed_rows(
        session, embedder, stale_prs,
        lambda x: pr_embed_text(x.title, x.body), "PRs",
    )

    session.commit()
    if total:
        logger.info("refresh_embeddings: embedded %s rows via %s", total, embedder.model_id)
    return total
