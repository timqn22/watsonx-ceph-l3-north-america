"""The dashboard renders real data (offline, hash embedder)."""

from __future__ import annotations

from app.dashboard import render_dashboard
from app.models import Issue, LinkSuggestion, PullRequest
from app.text import content_hash


def test_dashboard_renders_queue(session):
    session.add(
        Issue(
            id=1,
            subject="OSD crashes on startup",
            description="segfault on boot",
            is_open=True,
            content_hash=content_hash("a", "b"),
            url="https://tracker.ceph.com/issues/1",
        )
    )
    session.add(
        PullRequest(
            id="PR_1",
            repo_full_name="ceph/ceph",
            number=42,
            state="open",
            title="Fix osd crash on startup",
            body="resolves the segfault",
            referenced_issue_ids=[],
            content_hash=content_hash("c", "d"),
            url="https://github.com/ceph/ceph/pull/42",
        )
    )
    session.add(
        LinkSuggestion(pr_id="PR_1", issue_id=1, similarity=0.91, status="pending")
    )
    session.commit()

    html = render_dashboard(session, min_similarity=0.8, limit=50)

    assert "TrackerAssist" in html
    assert "Fix osd crash on startup" in html  # PR shows up
    assert "OSD crashes on startup" in html  # issue shows up
    assert "#42" in html and "ceph/ceph" in html
    assert "decide(" in html  # Accept/Ignore wiring present


def test_dashboard_threshold_hides_low_scores(session):
    session.add(
        Issue(id=1, subject="x", is_open=True, content_hash="h",
              url="https://tracker.ceph.com/issues/1")
    )
    session.add(
        PullRequest(id="PR_1", repo_full_name="ceph/ceph", number=1, state="open",
                    title="y", referenced_issue_ids=[], content_hash="h2",
                    url="https://github.com/ceph/ceph/pull/1")
    )
    session.add(
        LinkSuggestion(pr_id="PR_1", issue_id=1, similarity=0.60, status="pending")
    )
    session.commit()

    html = render_dashboard(session, min_similarity=0.80, limit=50)
    assert "No pending suggestions above this threshold" in html
