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
    full: bool = False  # clear the delta cursor and re-fetch everything


class ProfileIn(BaseModel):
    """Create/update a skill profile."""

    skill_prompt: str = ""
    background: str | None = None
    display_name: str | None = None
    preferred_projects: list[str] | None = None
    preferred_trackers: list[str] | None = None
    preferred_priorities: list[str] | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    display_name: str | None = None
    skill_prompt: str
    background: str | None = None
    preferred_projects: list[str] | None = None
    preferred_trackers: list[str] | None = None
    preferred_priorities: list[str] | None = None


class RecommendIn(BaseModel):
    """Request personalized issue recommendations.

    If ``skill_prompt`` is omitted, the stored profile's prompt is used.
    Filters override the profile's preferences when provided.
    """

    user: str | None = None  # signed-in identity; loads that saved profile
    skill_prompt: str | None = None
    # Free-text / tracker search. When set, ranks by this query instead of the
    # profile (e.g. "performance counters for bluestore" or "like tracker 77219").
    query: str | None = None
    projects: list[str] | None = None
    trackers: list[str] | None = None
    priorities: list[str] | None = None
    limit: int = 15
    # Recommend work already being handled by a PR? Off by default.
    include_in_progress: bool = False
    # Search only: narrow to open, unassigned, not-in-progress work. Off by
    # default so a search finds everything relevant (any state, claimed or not).
    only_unclaimed: bool = False


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
    # Claim status -- so search results can flag work that isn't actually free.
    assignee: str | None = None
    has_linked_pr: bool = False


class RelatedPrOut(BaseModel):
    """A PR related to an issue, for the issue-page panel."""

    relationship: str  # "linked" | "suggested"
    link_direction: str | None = None  # pr | tracker | both (for linked)
    similarity: float | None = None
    confidence: float | None = None  # calibrated 0..1 for display
    pr_number: int
    pr_repo: str
    pr_title: str | None = None
    pr_url: str | None = None
    state: str
    # Two-hop suggestions: this PR is linked to a similar tracker (not matched
    # directly), so the UI can say "via similar tracker #NNN".
    via_issue_id: int | None = None
    via_issue_subject: str | None = None


class SimilarIssueOut(BaseModel):
    """A tracker highly similar to the one being viewed (possible duplicate)."""

    issue_id: int
    subject: str | None = None
    url: str | None = None
    project_name: str | None = None
    tracker_name: str | None = None
    status: str | None = None
    is_open: bool
    assignee: str | None = None
    similarity: float
    confidence: float  # calibrated 0..1


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


class ProjectOut(BaseModel):
    name: str
    open_issues: int


class JobInfo(BaseModel):
    name: str
    next_run_time: str | None = None


class HealthOut(BaseModel):
    status: str
    db_ok: bool
    embedder: str
    reranker: str
    watsonx_configured: bool
    issues: int
    pull_requests: int
    pending_suggestions: int
    snapshot_cache: dict[str, object] = {}
    embed_cache: dict[str, int] = {}
    jobs: list[JobInfo]


class DuplicateGroupOut(BaseModel):
    """A group of similar trackers that may be duplicates."""

    trackers: list[SimilarIssueOut]
    max_confidence: float  # highest confidence in the group
    group_size: int
