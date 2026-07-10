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


class ProfileIn(BaseModel):
    """Create/update a skill profile."""

    skill_prompt: str = ""
    display_name: str | None = None
    preferred_projects: list[str] | None = None
    preferred_trackers: list[str] | None = None
    preferred_priorities: list[str] | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    display_name: str | None = None
    skill_prompt: str
    preferred_projects: list[str] | None = None
    preferred_trackers: list[str] | None = None
    preferred_priorities: list[str] | None = None


class RecommendIn(BaseModel):
    """Request personalized issue recommendations.

    If ``skill_prompt`` is omitted, the stored profile's prompt is used.
    Filters override the profile's preferences when provided.
    """

    skill_prompt: str | None = None
    projects: list[str] | None = None
    trackers: list[str] | None = None
    priorities: list[str] | None = None
    limit: int = 15
    # Recommend work already being handled by a PR? Off by default.
    include_in_progress: bool = False


class RecommendationOut(BaseModel):
    issue_id: int
    fit_score: int
    similarity: float
    reason: str
    is_stretch: bool
    subject: str | None = None
    tracker_name: str | None = None
    priority: str | None = None
    project_name: str | None = None
    url: str | None = None


class InProgressOut(BaseModel):
    """An open issue that already has a PR working on it."""

    issue_id: int
    subject: str | None = None
    issue_url: str | None = None
    assignee_login: str | None = None
    is_unassigned: bool
    evidence: str  # "referenced" | "match"
    similarity: float | None = None
    pr_number: int | None = None
    pr_repo: str | None = None
    pr_title: str | None = None
    pr_url: str | None = None


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
