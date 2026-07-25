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
    # A real link plus a lookalike PR -> show only the linked one. A recorded
    # link is the answer; speculative matches alongside it just add noise.
    _issue(session, 1, "rbd mirror snapshot replayer stuck", "replayer sync")
    _pr(session, "PR_link", 100, "rbd mirror fix",
        "Fixes: https://tracker.ceph.com/issues/1", referenced=[1], state="merged")
    _pr(session, "PR_sim", 101, "rbd mirror snapshot replayer stuck",
        "replayer sync work")  # similar text, but no reference
    session.commit()
    refresh_embeddings(session)

    rel = related_prs_for_issue(session, session.get(Issue, 1), min_similarity=0.0)
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


def test_tracker_side_link_marks_pr_linked(session):
    # The tracker references the PR (via its description), but the PR body does
    # NOT reference the tracker. It should still count as linked, flagged as
    # tracker-only.
    session.add(Issue(id=74854, subject="OSD stuff",
                      description="see https://github.com/ceph/ceph/pull/46912",
                      is_open=True, referenced_pr_numbers=[46912],
                      content_hash=content_hash("74854"),
                      url="https://tracker.ceph.com/issues/74854"))
    _pr(session, "PR_x", 46912, "some osd fix", "no tracker reference here")
    session.commit()
    refresh_embeddings(session)

    rel = related_prs_for_issue(session, session.get(Issue, 74854))
    assert len(rel) == 1
    assert rel[0].relationship == "linked"
    assert rel[0].link_direction == "tracker"  # PR has no back-reference
    assert rel[0].pr.number == 46912


def test_extra_pr_numbers_from_page_count_as_linked(session):
    # Issue has no stored PR reference (e.g. the link was only in a comment),
    # but the caller passes the PR number it found on the page.
    _issue(session, 5, "some osd bug", "no reference stored here")
    _pr(session, "PR_x", 46912, "osd fix", "no tracker reference")
    session.commit()
    refresh_embeddings(session)

    # Without the hint -> not linked (at most a weak suggestion).
    plain = related_prs_for_issue(session, session.get(Issue, 5))
    assert not any(r.relationship == "linked" for r in plain)

    # With the page-scanned PR number -> linked (tracker side).
    rel = related_prs_for_issue(
        session, session.get(Issue, 5), extra_pr_numbers={46912}
    )
    assert rel[0].relationship == "linked"
    assert rel[0].link_direction == "tracker"
    assert rel[0].pr.number == 46912


def test_duplicate_warning_flags_near_identical_tracker(session, monkeypatch):
    # A new report nearly identical to an existing (closed) tracker is flagged;
    # an unrelated issue is not. Closed duplicates matter most -- "already fixed".
    from app.ai.linkage import similar_trackers_for_issue
    from app.config import get_settings

    _issue(session, 80001, "OSD crashes on bluestore cache trim",
           "osd segfault during bluestore cache trim under load")
    session.add(Issue(id=60001, subject="OSD segfault in bluestore cache trim",
                      description="osd crashes bluestore cache trim under heavy load",
                      is_open=False, status="Resolved",
                      content_hash=content_hash("dup"),
                      url="https://tracker.ceph.com/issues/60001"))
    _issue(session, 70002, "rgw multisite sync stuck",
           "radosgw multisite replication stall")
    session.commit()
    refresh_embeddings(session)

    monkeypatch.setenv("DUPLICATE_MIN_SIMILARITY", "0.5")  # hash-embedder scale
    get_settings.cache_clear()
    try:
        dups = similar_trackers_for_issue(session, session.get(Issue, 80001), floor=0.1)
        none = similar_trackers_for_issue(session, session.get(Issue, 70002), floor=0.1)
    finally:
        get_settings.cache_clear()

    assert [d.issue.id for d in dups] == [60001]
    assert dups[0].issue.is_open is False  # closed trackers are included
    assert none == []  # unrelated issue stays quiet


def test_pr_reference_parsing_from_description_and_field():
    from app.text import parse_referenced_pr_numbers

    desc = "Fixed by https://github.com/ceph/ceph/pull/46912 and see /pull/100"
    assert parse_referenced_pr_numbers(desc, None) == [46912]
    cf = [{"name": "Pull request ID", "value": "51234"}]
    assert parse_referenced_pr_numbers(None, cf) == [51234]


def test_two_hop_surfaces_similar_trackers_linked_pr(session, monkeypatch):
    # Two-hop retrieval: this tracker has no PR of its own, but a very similar
    # tracker DOES have a recorded fix -- that PR should surface first, labeled
    # with the tracker it came via.
    from app.config import get_settings

    _issue(session, 77219, "Measure BlueStore caches performance",
           "measure bluestore cache perf counters hit miss")
    _issue(session, 77226, "Performance counters for ObjectStore interface",
           "bluestore perf counters measure cache interface")
    _pr(session, "PR_SIB", 70200, "os/bluestore: add perf counters",
        "Fixes: https://tracker.ceph.com/issues/77226", referenced=[77226],
        state="merged")
    session.commit()
    refresh_embeddings(session)

    # Hash-embedder cosines sit lower than Granite's, so drop the two-hop bar.
    monkeypatch.setenv("RELATED_VIA_ISSUE_MIN_SIMILARITY", "0.2")
    get_settings.cache_clear()
    try:
        rel = related_prs_for_issue(
            session, session.get(Issue, 77219), min_similarity=0.99, floor=0.1
        )
    finally:
        get_settings.cache_clear()

    assert rel, "expected the sibling tracker's PR to surface"
    assert rel[0].pr.number == 70200
    assert rel[0].relationship == "suggested"
    assert rel[0].via_issue_id == 77226
    assert "ObjectStore" in (rel[0].via_issue_subject or "")


def test_similar_unlinked_pr_is_suggested(session):
    _issue(session, 1, "rbd mirror snapshot replayer stuck",
           "the rbd-mirror image replayer hangs during snapshot sync")
    _pr(session, "PR_1", 10, "rbd mirror snapshot replayer stuck",
        "fix the rbd-mirror image replayer hang during snapshot sync")  # no reference
    session.commit()
    refresh_embeddings(session)

    rel = related_prs_for_issue(session, session.get(Issue, 1), min_similarity=0.3)
    assert any(r.relationship == "suggested" and r.pr.number == 10 for r in rel)
