"""End-to-end test of the embed -> match -> suggest pipeline.

Uses the HashEmbedder, so a PR that shares vocabulary with an issue produces a
real cosine match without any model download or credentials.
"""

from __future__ import annotations

from app.ai.linkage import rebuild_suggestions, suggest_links_for_pr
from app.models import Issue, LinkSuggestion, PullRequest
from app.services.indexer import refresh_embeddings
from app.text import content_hash


def _issue(session, id_, subject, description):
    session.add(
        Issue(
            id=id_,
            subject=subject,
            description=description,
            is_open=True,
            content_hash=content_hash(subject, description),
            updated_on="2024-01-01T00:00:00Z",
            url=f"https://tracker.ceph.com/issues/{id_}",
        )
    )


def _pr(session, id_, title, body, referenced=None):
    session.add(
        PullRequest(
            id=id_,
            repo_full_name="ceph/ceph",
            number=int(id_.split("_")[-1]) if "_" in id_ else 1,
            state="open",
            title=title,
            body=body,
            referenced_issue_ids=referenced or [],
            content_hash=content_hash(title, body),
            updated_at="2024-01-02T00:00:00Z",
            url="https://github.com/ceph/ceph/pull/1",
        )
    )


def test_matching_pr_is_suggested(session):
    _issue(session, 1, "OSD daemon crashes on startup with segfault",
           "The ceph-osd process crashes immediately on boot due to a null pointer")
    _issue(session, 2, "Documentation typo in rados manpage",
           "Fix a small spelling mistake in the docs")
    _pr(session, "PR_1", "Fix ceph-osd crash on startup",
        "This fixes the null pointer segfault when the osd daemon boots")
    session.commit()

    refresh_embeddings(session)
    pr = session.get(PullRequest, "PR_1")
    matches = suggest_links_for_pr(session, pr, min_similarity=0.05, limit=5)

    assert matches, "expected at least one suggestion"
    assert matches[0].issue_id == 1  # the OSD-crash issue, not the docs typo


def test_already_linked_pr_is_skipped(session):
    _issue(session, 1, "OSD daemon crashes on startup", "segfault on boot")
    _pr(session, "PR_1", "Fix osd crash", "fixes the osd crash on boot",
        referenced=[1])
    session.commit()

    refresh_embeddings(session)
    pr = session.get(PullRequest, "PR_1")
    matches = suggest_links_for_pr(session, pr, min_similarity=0.0, limit=5)
    assert matches == []  # references issue #1 already -> considered linked


def test_rebuild_suggestions_populates_cache_and_preserves_decisions(session):
    _issue(session, 1, "OSD daemon crashes on startup with segfault",
           "null pointer in ceph-osd on boot")
    _pr(session, "PR_1", "Fix ceph-osd crash on startup",
        "resolves the segfault in the osd daemon on boot")
    session.commit()

    refresh_embeddings(session)
    pending = rebuild_suggestions(session, min_similarity=0.05)
    assert pending >= 1

    # Reject it, then rebuild again -> the rejection must survive.
    s = session.query(LinkSuggestion).first()
    s.status = "rejected"
    session.commit()

    rebuild_suggestions(session, min_similarity=0.05)
    survived = session.get(LinkSuggestion, s.id)
    assert survived is not None and survived.status == "rejected"
