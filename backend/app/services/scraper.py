"""Scraping services: pull from Redmine/GitHub into the database.

Each sync function is idempotent (upsert by primary key) and delta-aware (uses
the ScrapeState cursor so repeated runs only fetch what changed). A Redmine
sync can also ingest from a local folder of raw ``*.json`` files produced by the
original prototype's scraper -- so an existing scrape isn't wasted.
"""

from __future__ import annotations

import glob
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..clients.github import GitHubClient
from ..clients.redmine import RedmineClient
from ..models import Issue, PullRequest, ScrapeState
from ..text import normalize_github_pull, normalize_redmine_issue

logger = logging.getLogger(__name__)


def _get_state(session: Session, source: str) -> ScrapeState:
    state = session.get(ScrapeState, source)
    if state is None:
        state = ScrapeState(source=source)
        session.add(state)
    return state


def _finish_state(
    state: ScrapeState, *, cursor: str | None, ok: bool, error: str | None
) -> None:
    if cursor:
        state.last_cursor = cursor
    state.last_run_at = datetime.now(timezone.utc)
    state.last_status = "ok" if ok else "error"
    state.last_error = error


def _upsert_issue(session: Session, fields: dict[str, Any]) -> None:
    """Insert or update an Issue, re-embedding only if content changed."""
    existing = session.get(Issue, fields["id"])
    if existing is None:
        session.add(Issue(**fields, scraped_at=datetime.now(timezone.utc)))
        return
    for key, value in fields.items():
        setattr(existing, key, value)
    existing.scraped_at = datetime.now(timezone.utc)
    # embedded_hash stays as-is; the indexer compares it to content_hash.


def _upsert_pull(session: Session, fields: dict[str, Any]) -> None:
    existing = session.get(PullRequest, fields["id"])
    if existing is None:
        session.add(PullRequest(**fields, scraped_at=datetime.now(timezone.utc)))
        return
    for key, value in fields.items():
        setattr(existing, key, value)
    existing.scraped_at = datetime.now(timezone.utc)


def _iter_raw_issue_files(directory: str):
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            # The prototype saved either the bare issue or {"issue": {...}}.
            yield data.get("issue", data) if isinstance(data, dict) else data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("skipping raw issue file %s: %s", path, exc)


def sync_redmine(
    session: Session, *, status: str, settings: Settings | None = None
) -> int:
    """Sync Redmine issues for ``status`` ('open' or 'closed'). Returns count."""
    settings = settings or get_settings()
    source = f"redmine_{status}"
    state = _get_state(session, source)
    count = 0
    latest_cursor = state.last_cursor
    try:
        if settings.raw_issues_dir and status == "open":
            # Offline ingest from the prototype's saved JSON.
            logger.info("Ingesting Redmine issues from %s", settings.raw_issues_dir)
            for raw in _iter_raw_issue_files(settings.raw_issues_dir):
                fields = normalize_redmine_issue(raw, settings.redmine_url)
                if fields["id"] is None:
                    continue
                # Respect the status filter for the folder ingest too.
                if status == "open" and not fields["is_open"]:
                    continue
                _upsert_issue(session, fields)
                count += 1
        else:
            client = RedmineClient(settings.redmine_url, settings.redmine_api_key)
            try:
                for raw in client.iter_issues(
                    project_id=settings.redmine_project_id,
                    status=status,
                    updated_since=state.last_cursor,
                    max_issues=settings.max_issues,
                ):
                    fields = normalize_redmine_issue(raw, settings.redmine_url)
                    if fields["id"] is None:
                        continue
                    _upsert_issue(session, fields)
                    count += 1
                    if fields["updated_on"] and (
                        latest_cursor is None or fields["updated_on"] > latest_cursor
                    ):
                        latest_cursor = fields["updated_on"]
            finally:
                client.close()
        _finish_state(state, cursor=latest_cursor, ok=True, error=None)
        session.commit()
        logger.info("sync_redmine(%s): upserted %s issues", status, count)
    except Exception as exc:
        session.rollback()
        state = _get_state(session, source)
        _finish_state(state, cursor=None, ok=False, error=str(exc))
        session.commit()
        logger.exception("sync_redmine(%s) failed", status)
    return count


def sync_github(
    session: Session, *, state_name: str, pr_state: str, settings: Settings | None = None
) -> int:
    """Sync GitHub pulls across all configured repos. Returns count."""
    settings = settings or get_settings()
    source = f"github_{state_name}"
    state = _get_state(session, source)
    count = 0
    latest_cursor = state.last_cursor
    try:
        client = GitHubClient(settings.github_token)
        try:
            for repo in settings.github_repo_list:
                for raw in client.iter_pulls(
                    repo,
                    state=pr_state,
                    updated_since=state.last_cursor,
                    max_pulls=settings.max_pulls,
                ):
                    fields = normalize_github_pull(raw, repo)
                    if not fields["id"]:
                        continue
                    _upsert_pull(session, fields)
                    count += 1
                    if fields["updated_at"] and (
                        latest_cursor is None or fields["updated_at"] > latest_cursor
                    ):
                        latest_cursor = fields["updated_at"]
        finally:
            client.close()
        _finish_state(state, cursor=latest_cursor, ok=True, error=None)
        session.commit()
        logger.info("sync_github(%s): upserted %s pulls", pr_state, count)
    except Exception as exc:
        session.rollback()
        state = _get_state(session, source)
        _finish_state(state, cursor=None, ok=False, error=str(exc))
        session.commit()
        logger.exception("sync_github(%s) failed", pr_state)
    return count
