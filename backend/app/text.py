"""Text helpers: normalization of raw API payloads into ORM-ready dicts.

Keeps the messy shape-of-the-JSON logic in one place so scrapers stay short.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Matches both a bare "#12345" and a Redmine issue URL ".../issues/12345".
# Ceph's convention is "Fixes: https://tracker.ceph.com/issues/12345", so the
# URL form is the reliable already-linked signal; the "#id" form is a bonus.
_ISSUE_REF_RE = re.compile(r"(?:/issues/|#)(\d+)")
# A GitHub pull request URL, e.g. https://github.com/ceph/ceph/pull/46912
_PR_URL_RE = re.compile(r"github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")


def content_hash(*parts: str | None) -> str:
    """Stable sha256 over the given text parts (drives re-embedding)."""
    joined = "\n".join(p or "" for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def issue_embed_text(subject: str | None, description: str | None) -> str:
    """The text we feed the embedder for an issue."""
    return f"{subject or ''}\n\n{description or ''}".strip()


def pr_embed_text(title: str | None, body: str | None) -> str:
    """The text we feed the embedder for a pull request."""
    return f"{title or ''}\n\n{body or ''}".strip()


def parse_referenced_issue_ids(body: str | None) -> list[int]:
    """Extract already-referenced tracker issue ids from a PR body.

    Catches both ``#1234`` and Redmine URLs like
    ``https://tracker.ceph.com/issues/1234`` (Ceph's ``Fixes:`` convention).
    These are treated as existing links so the matcher only surfaces *missing*
    ones. Deduplicated, order-preserving.
    """
    if not body:
        return []
    seen: dict[int, None] = {}
    for m in _ISSUE_REF_RE.findall(body):
        seen.setdefault(int(m), None)
    return list(seen.keys())


def parse_referenced_pr_numbers(
    description: str | None, custom_fields: list[dict[str, Any]] | None
) -> list[int]:
    """PR numbers a tracker points at: a GitHub PR URL in the description, or a
    "Pull request ID" custom field. This is the *tracker -> PR* link direction,
    which the PR body may not mirror. Deduplicated, order-preserving.
    """
    nums: dict[int, None] = {}
    if description:
        for m in _PR_URL_RE.findall(description):
            nums.setdefault(int(m), None)
    for field in custom_fields or []:
        value = field.get("value")
        if not value:
            continue
        values = value if isinstance(value, list) else [value]
        name = (field.get("name") or "").lower()
        for v in values:
            v = str(v).strip()
            for m in _PR_URL_RE.findall(v):
                nums.setdefault(int(m), None)
            # A bare number in a pull-request-ish field.
            if "pull request" in name and v.isdigit():
                nums.setdefault(int(v), None)
    return list(nums.keys())


def normalize_redmine_issue(raw: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Map a Redmine issue payload to Issue-model kwargs."""
    subject = raw.get("subject", "") or ""
    description = raw.get("description") or ""
    status_name = (raw.get("status") or {}).get("name")
    is_closed = bool(raw.get("closed_on")) or (
        (raw.get("status") or {}).get("is_closed", False)
    )
    return {
        "id": raw.get("id"),
        "project_id": (raw.get("project") or {}).get("id"),
        "project_name": (raw.get("project") or {}).get("name"),
        "tracker_name": (raw.get("tracker") or {}).get("name"),
        "status": status_name,
        "priority": (raw.get("priority") or {}).get("name"),
        "subject": subject,
        "description": description,
        "author_login": (raw.get("author") or {}).get("name"),
        "assignee_login": (raw.get("assigned_to") or {}).get("name"),
        "created_on": raw.get("created_on"),
        "updated_on": raw.get("updated_on"),
        "closed_on": raw.get("closed_on"),
        "is_open": not is_closed,
        "url": f"{base_url.rstrip('/')}/issues/{raw.get('id')}",
        "content_hash": content_hash(subject, description),
        "referenced_pr_numbers": parse_referenced_pr_numbers(
            description, raw.get("custom_fields")
        ),
    }


def normalize_github_pull(raw: dict[str, Any], repo_full_name: str) -> dict[str, Any]:
    """Map a GitHub pull payload to PullRequest-model kwargs."""
    title = raw.get("title", "") or ""
    body = raw.get("body") or ""
    if raw.get("merged_at"):
        state = "merged"
    else:
        state = raw.get("state", "open")
    return {
        "id": str(raw.get("node_id") or raw.get("id")),
        "repo_full_name": repo_full_name,
        "number": raw.get("number"),
        "state": state,
        "title": title,
        "body": body,
        "author_login": (raw.get("user") or {}).get("login"),
        "base_branch": (raw.get("base") or {}).get("ref"),
        "head_branch": (raw.get("head") or {}).get("ref"),
        "referenced_issue_ids": parse_referenced_issue_ids(body),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "merged_at": raw.get("merged_at"),
        "url": raw.get("html_url"),
        "content_hash": content_hash(title, body),
    }
