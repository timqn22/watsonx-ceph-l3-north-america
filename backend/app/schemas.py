"""Pydantic response/request schemas.

Every API response is an explicit model so the contract with the browser
extension is stable and self-documenting.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_name: str | None = None
    tracker_name: str | None = None
    status: str | None = None
    priority: str | None = None
    subject: str
    author_login: str | None = None
    assignee_login: str | None = None
    updated_on: str | None = None
    is_open: bool
    url: str | None = None


class PullRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repo_full_name: str
    number: int
    state: str
    title: str
    author_login: str | None = None
    referenced_issue_ids: list[int] | None = None
    updated_at: str | None = None
    url: str | None = None


class LinkSuggestionOut(BaseModel):
    """A single PR<->issue suggestion, enriched for the UI."""

    id: int
    pr_id: str
    issue_id: int
    similarity: float
    status: str
    model_id: str | None = None
    created_at: datetime

    # Enriched fields for display (populated by the repository layer).
    pr_number: int | None = None
    pr_repo: str | None = None
    pr_title: str | None = None
    pr_url: str | None = None
    issue_subject: str | None = None
    issue_url: str | None = None


class DecisionIn(BaseModel):
    """Body for accepting/rejecting/ignoring a suggestion."""

    status: str  # accepted | rejected | ignored
    decided_by: str | None = None


class RescrapeIn(BaseModel):
    """Body for the admin force-rescrape endpoint."""

    source: str  # redmine_open | redmine_closed | github_open | github_closed


class JobInfo(BaseModel):
    name: str
    next_run_time: str | None = None


class HealthOut(BaseModel):
    status: str
    db_ok: bool
    embedder: str
    watsonx_configured: bool
    issues: int
    pull_requests: int
    pending_suggestions: int
    jobs: list[JobInfo]
