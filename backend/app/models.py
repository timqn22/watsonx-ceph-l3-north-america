"""SQLAlchemy ORM models.

Four tables:
  * Issue           -- a Redmine issue (the "tracker" side)
  * PullRequest     -- a GitHub pull request
  * ScrapeState     -- delta-polling cursor + last-run status per source
  * LinkSuggestion  -- a cached PR<->issue linkage suggestion with a decision

Embeddings are stored as JSON arrays of floats. At hackathon scale this is fine
and keeps the schema database-agnostic; similarity search runs in Python.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Issue(Base):
    """A Redmine issue. Primary key is the Redmine issue id."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(Integer, index=True)
    project_name: Mapped[str | None] = mapped_column(String(255))
    tracker_name: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    priority: Mapped[str | None] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(1024), default="")
    description: Mapped[str | None] = mapped_column(Text)
    author_login: Mapped[str | None] = mapped_column(String(255))
    assignee_login: Mapped[str | None] = mapped_column(String(255))
    created_on: Mapped[str | None] = mapped_column(String(64))
    updated_on: Mapped[str | None] = mapped_column(String(64), index=True)
    closed_on: Mapped[str | None] = mapped_column(String(64))
    is_open: Mapped[bool] = mapped_column(default=True, index=True)
    url: Mapped[str | None] = mapped_column(String(512))

    # sha256 of subject+description; drives re-embedding.
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    embedded_hash: Mapped[str | None] = mapped_column(String(64))
    embedding: Mapped[list[float] | None] = mapped_column(JSON)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PullRequest(Base):
    """A GitHub pull request. Primary key is the GitHub node id (stable)."""

    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    number: Mapped[int] = mapped_column(Integer, index=True)
    state: Mapped[str] = mapped_column(String(16), index=True)  # open|closed|merged
    title: Mapped[str] = mapped_column(String(1024), default="")
    body: Mapped[str | None] = mapped_column(Text)
    author_login: Mapped[str | None] = mapped_column(String(255))
    base_branch: Mapped[str | None] = mapped_column(String(255))
    head_branch: Mapped[str | None] = mapped_column(String(255))

    # Redmine issue ids parsed from the PR body (e.g. "#1234"). Best-effort.
    referenced_issue_ids: Mapped[list[int] | None] = mapped_column(JSON)

    created_at: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[str | None] = mapped_column(String(64), index=True)
    merged_at: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(512))

    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    embedded_hash: Mapped[str | None] = mapped_column(String(64))
    embedding: Mapped[list[float] | None] = mapped_column(JSON)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ScrapeState(Base):
    """Delta-polling cursor and last-run bookkeeping for one source."""

    __tablename__ = "scrape_state"

    # e.g. redmine_open, redmine_closed, github_open, github_closed
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_cursor: Mapped[str | None] = mapped_column(String(64))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_status: Mapped[str | None] = mapped_column(String(32))
    last_error: Mapped[str | None] = mapped_column(Text)


class UserProfile(Base):
    """A person's skill profile, used to personalize task recommendations.

    Single-user demos use ``external_id="me"``. The skill_prompt is free text;
    its embedding is cached so recommendations don't re-embed it every request.
    """

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    skill_prompt: Mapped[str] = mapped_column(Text, default="")
    # Free-text background: previous projects / experience, folded into the
    # embedding alongside skills for richer recommendations.
    background: Mapped[str | None] = mapped_column(Text)

    preferred_projects: Mapped[list[str] | None] = mapped_column(JSON)
    preferred_trackers: Mapped[list[str] | None] = mapped_column(JSON)
    preferred_priorities: Mapped[list[str] | None] = mapped_column(JSON)

    skill_embedding: Mapped[list[float] | None] = mapped_column(JSON)
    skill_embedded_hash: Mapped[str | None] = mapped_column(String(64))

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class LinkSuggestion(Base):
    """A cached suggestion that a PR and an issue should be linked."""

    __tablename__ = "link_suggestions"
    __table_args__ = (UniqueConstraint("pr_id", "issue_id", name="uq_pr_issue"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[str] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    similarity: Mapped[float] = mapped_column(Float)
    model_id: Mapped[str | None] = mapped_column(String(128))
    # pending | accepted | rejected | ignored
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decided_by: Mapped[str | None] = mapped_column(String(255))

    pr: Mapped[PullRequest] = relationship()
    issue: Mapped[Issue] = relationship()
