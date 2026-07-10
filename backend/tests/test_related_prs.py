"""Issue-page 'related PRs' includes already-linked and merged PRs."""

from __future__ import annotations

from app.ai.linkage import calibrate, related_prs_for_issue
from app.models import Issue, PullRequest
from app.services.indexer import refresh_embeddings
from app.text import content_hash


def _issue(session, id_, subject, desc):
    session.add(Issue(id=id_, subject=subject, description=desc, is_open=True,
                      content_hash=content_hash(subject, desc),
                      url=f"https://tracker.ceph.com/issues/{id_}"))


def _pr(session, id_, num, title, body, *, referenced=None, state="open"):
    session.add(PullRequest(id=id_, repo_full_name="ceph/ceph", number=num, state=state,
                            title=title, body=body, referenced_issue_ids=referenced or [],
                            content_hash=content_hash(title, body),
                            url=f"https://github.com/ceph/ceph/pull/{num}"))


def test_already_linked_pr_is_shown(session):
    # This is the case the missing-link view hides but the issue page must show.
    _issue(session, 77226, "Performance counters for ObjectStore interface",
           "cover BlueStore functions with perf counters")
    _pr(session, "PR_1", 100, "bluestore: add perf counters",
        "Fixes: https://tracker.ceph.com/issues/77226", referenced=[77226],
        state="merged")
    session.commit()
    refresh_embeddings(session)

    rel = related_prs_for_issue(session, session.get(Issue, 77226))
    assert rel, "expected the linked PR to be returned"
    assert rel[0].relationship == "linked"
    assert rel[0].pr.number == 100
    assert rel[0].pr.state == "merged"  # merged PRs are included


def test_linked_pr_suppresses_speculative_matches(session):
    # A real link plus a lookalike PR -> show only the linked one.
    _issue(session, 1, "rbd mirror snapshot replayer stuck", "replayer sync")
    _pr(session, "PR_link", 100, "rbd mirror fix",
        "Fixes: https://tracker.ceph.com/issues/1", referenced=[1], state="merged")
    _pr(session, "PR_sim", 101, "rbd mirror snapshot replayer stuck",
        "replayer sync work")  # similar text, but no reference
    session.commit()
    refresh_embeddings(session)

    rel = related_prs_for_issue(session, session.get(Issue, 1))
    assert {r.pr.number for r in rel} == {100}
    assert all(r.relationship == "linked" for r in rel)


def test_related_prs_capped_at_three(session):
    _issue(session, 1, "rbd mirror snapshot replayer", "replayer sync")
    for n in range(5):
        _pr(session, f"PR_{n}", 200 + n, "rbd mirror snapshot replayer",
            "replayer sync work")
    session.commit()
    refresh_embeddings(session)
    rel = related_prs_for_issue(session, session.get(Issue, 1), min_similarity=0.0)
    assert len(rel) <= 3


def test_calibration_removes_baseline():
    assert calibrate(0.70, 0.70) == 0.0
    assert calibrate(1.0, 0.70) == 1.0
    # A raw 0.77 is a modest ~23% once the 0.70 baseline is removed.
    assert 0.2 < calibrate(0.77, 0.70) < 0.3


def test_similar_unlinked_pr_is_suggested(session):
    _issue(session, 1, "rbd mirror snapshot replayer stuck",
           "the rbd-mirror image replayer hangs during snapshot sync")
    _pr(session, "PR_1", 10, "rbd mirror snapshot replayer stuck",
        "fix the rbd-mirror image replayer hang during snapshot sync")  # no reference
    session.commit()
    refresh_embeddings(session)

    rel = related_prs_for_issue(session, session.get(Issue, 1), min_similarity=0.3)
    assert any(r.relationship == "suggested" and r.pr.number == 10 for r in rel)
