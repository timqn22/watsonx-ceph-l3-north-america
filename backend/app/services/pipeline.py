"""Composed pipeline runs used by both the scheduler and the admin endpoint.

Each entry point owns its own DB session so it is safe to call from a background
scheduler thread.
"""

from __future__ import annotations

import logging

from ..config import get_settings
from ..db import SessionLocal
from .indexer import refresh_embeddings
from ..ai.linkage import rebuild_suggestions
from .scraper import sync_github, sync_redmine

logger = logging.getLogger(__name__)


def _index_and_match(session) -> None:
    """Embed anything new, then recompute the suggestion cache."""
    refresh_embeddings(session)
    rebuild_suggestions(
        session, min_similarity=get_settings().link_min_similarity
    )


def run_open_cycle() -> None:
    """Poll open issues + open PRs, embed, and refresh suggestions."""
    with SessionLocal() as session:
        sync_redmine(session, status="open")
        sync_github(session, state_name="open", pr_state="open")
        _index_and_match(session)


def run_closed_cycle() -> None:
    """Drift catch for closed items (runs less often)."""
    with SessionLocal() as session:
        sync_redmine(session, status="closed")
        sync_github(session, state_name="closed", pr_state="closed")
        refresh_embeddings(session)


def run_source(source: str) -> None:
    """Force a single named source sync (for the admin/demo endpoint)."""
    with SessionLocal() as session:
        if source == "redmine_open":
            sync_redmine(session, status="open")
        elif source == "redmine_closed":
            sync_redmine(session, status="closed")
        elif source == "github_open":
            sync_github(session, state_name="open", pr_state="open")
        elif source == "github_closed":
            sync_github(session, state_name="closed", pr_state="closed")
        else:
            raise ValueError(f"unknown source: {source}")
        _index_and_match(session)
