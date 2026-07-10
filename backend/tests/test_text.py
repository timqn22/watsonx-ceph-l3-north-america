"""Unit tests for payload normalization + reference parsing."""

from __future__ import annotations

from app.text import (
    normalize_github_pull,
    normalize_redmine_issue,
    parse_referenced_issue_ids,
)


def test_parse_referenced_issue_ids_dedupes_and_orders():
    assert parse_referenced_issue_ids("fixes #42 and #7, also #42") == [42, 7]
    assert parse_referenced_issue_ids(None) == []
    assert parse_referenced_issue_ids("no refs here") == []


def test_parse_referenced_issue_ids_matches_tracker_urls():
    # Ceph's convention: a full tracker URL, not "#id".
    body = "Fixes: https://tracker.ceph.com/issues/68450\nSigned-off-by: x"
    assert parse_referenced_issue_ids(body) == [68450]
    # URL and bare-ref forms dedupe to the same id.
    assert parse_referenced_issue_ids(
        "see https://tracker.ceph.com/issues/5 and #5"
    ) == [5]


def test_normalize_redmine_issue_marks_closed():
    raw = {
        "id": 5,
        "subject": "OSD crash",
        "description": "segfault",
        "status": {"name": "Closed", "is_closed": True},
        "project": {"id": 1, "name": "rbd"},
        "closed_on": "2024-01-01T00:00:00Z",
    }
    fields = normalize_redmine_issue(raw, "https://tracker.ceph.com")
    assert fields["id"] == 5
    assert fields["is_open"] is False
    assert fields["url"].endswith("/issues/5")
    assert fields["content_hash"]


def test_normalize_github_pull_detects_merged():
    raw = {
        "node_id": "PR_abc",
        "number": 12,
        "title": "Fix OSD crash",
        "body": "closes #5",
        "state": "closed",
        "merged_at": "2024-02-02T00:00:00Z",
        "user": {"login": "octocat"},
        "html_url": "https://github.com/ceph/ceph/pull/12",
    }
    fields = normalize_github_pull(raw, "ceph/ceph")
    assert fields["id"] == "PR_abc"
    assert fields["state"] == "merged"
    assert fields["referenced_issue_ids"] == [5]
