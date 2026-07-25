"""Feature B: skill-based recommendations (hash embedder, offline)."""

from __future__ import annotations

from app.models import Issue
from app.services.indexer import refresh_embeddings
from app.services.recommendations import get_or_create_profile, recommend_issues
from app.text import content_hash


def _issue(session, id_, subject, description, *, tracker="Bug", priority="Normal",
           project="RBD", is_open=True):
    session.add(
        Issue(
            id=id_, subject=subject, description=description, tracker_name=tracker,
            priority=priority, project_name=project, is_open=is_open,
            content_hash=content_hash(subject, description),
            url=f"https://tracker.ceph.com/issues/{id_}",
        )
    )


def test_recommends_by_skill_overlap(session):
    _issue(session, 1, "rbd mirror snapshot replayer stuck",
           "rbd-mirror image replayer hangs during snapshot sync")
    _issue(session, 2, "cephfs quota metrics wrong",
           "subvolume used_bytes not updated after quota reset")
    _issue(session, 3, "docs typo in manpage", "fix spelling in rados docs")
    session.commit()
    refresh_embeddings(session)

    recs = recommend_issues(
        session,
        skill_prompt="I work on rbd mirror snapshot replayer internals",
        limit=3,
        stretch=0,
    )
    assert recs, "expected recommendations"
    assert recs[0].issue_id == 1  # the rbd-mirror issue ranks first
    assert recs[0].fit_score >= recs[-1].fit_score  # sorted by fit
    # FIT is relative to the best match: the top pick reads high (100), not a
    # tiny raw-cosine number like "27". Weaker picks taper down from there.
    assert recs[0].fit_score == 100


def test_filters_restrict_candidates(session):
    _issue(session, 1, "rbd mirror snapshot", "rbd mirror work", project="RBD")
    _issue(session, 2, "rbd mirror snapshot in cephfs", "same words", project="CephFS")
    session.commit()
    refresh_embeddings(session)

    recs = recommend_issues(
        session, skill_prompt="rbd mirror snapshot", projects=["CephFS"], stretch=0
    )
    assert {r.issue_id for r in recs} == {2}  # only the CephFS project issue


def test_closed_issues_excluded(session):
    _issue(session, 1, "rbd mirror snapshot", "open work", is_open=True)
    _issue(session, 2, "rbd mirror snapshot", "closed work", is_open=False)
    session.commit()
    refresh_embeddings(session)

    recs = recommend_issues(session, skill_prompt="rbd mirror snapshot", stretch=0)
    assert all(r.issue_id != 2 for r in recs)


def test_assigned_issues_are_not_recommended(session):
    _issue(session, 1, "rbd mirror snapshot", "rbd mirror work")  # unassigned
    session.add(
        Issue(id=2, subject="rbd mirror snapshot other", description="rbd mirror",
              is_open=True, assignee_login="someone", content_hash=content_hash("2"),
              url="https://tracker.ceph.com/issues/2")
    )
    session.commit()
    refresh_embeddings(session)

    recs = recommend_issues(session, skill_prompt="rbd mirror snapshot", stretch=0)
    ids = {r.issue_id for r in recs}
    assert 1 in ids and 2 not in ids  # assigned issue #2 is excluded


def test_explicit_project_filter_overrides(session):
    _issue(session, 1, "bluestore perf", "counters", project="bluestore")
    _issue(session, 2, "bluestore perf other", "counters", project="RADOS")
    session.commit()
    refresh_embeddings(session)

    # Only RADOS selected -> only the RADOS issue, ranked by similarity as usual.
    recs = recommend_issues(
        session, skill_prompt="bluestore perf counters", projects=["RADOS"], stretch=0
    )
    assert {r.issue_id for r in recs} == {2}

    # No project filter -> both projects considered.
    recs_all = recommend_issues(
        session, skill_prompt="bluestore perf counters", projects=None, stretch=0
    )
    assert {r.issue_id for r in recs_all} == {1, 2}


def test_component_affinity_breaks_ties(session):
    # Two issues with identical text (equal content score) in different
    # components; affinity for RADOS should rank the RADOS one first.
    _issue(session, 1, "generic ceph work", "do a thing", project="RBD")
    _issue(session, 2, "generic ceph work", "do a thing", project="RADOS")
    session.commit()
    refresh_embeddings(session)

    # No affinity -> tie (order not guaranteed); with RADOS affinity -> #2 first.
    recs = recommend_issues(
        session, skill_prompt="generic ceph work", stretch=0,
        affinity_components={"rados"}, affinity_weight=0.05,
    )
    assert recs[0].issue_id == 2


def test_search_by_free_text(session):
    from app.ai.embedder import get_embedder
    from app.services.recommendations import recommend_issues, resolve_query_vector

    _issue(session, 1, "bluestore perf counters", "add perf counters to bluestore")
    _issue(session, 2, "docs typo", "fix spelling in docs")
    session.commit()
    refresh_embeddings(session)

    qvec, excl, text = resolve_query_vector(
        session, "performance counters for bluestore", get_embedder()
    )
    recs = recommend_issues(
        session, skill_prompt=text, query_vector=qvec, stretch=0, exclude_assigned=False
    )
    assert recs and recs[0].issue_id == 1  # the matching issue ranks first
    assert recs[0].fit_score == 100  # relative fit still applies in search


def test_search_hybrid_surfaces_exact_title(session):
    # Dense similarity alone can bury an exact-title match under other same-topic
    # issues; the lexical half of hybrid search must lift it to the top.
    from app.ai.embedder import get_embedder
    from app.services.recommendations import recommend_issues, resolve_query_vector

    _issue(session, 1, "Measure BlueStore caches performance", "measure bluestore cache perf")
    _issue(session, 2, "Memory recommendations for bluestore", "bluestore memory tuning")
    _issue(session, 3, "BlueStore fragmentation latency", "bluestore fragmentation")
    session.commit()
    refresh_embeddings(session)

    qvec, excl, text = resolve_query_vector(
        session, "Measure BlueStore caches performance", get_embedder()
    )
    recs = recommend_issues(
        session, skill_prompt=text, query_vector=qvec, stretch=0,
        exclude_assigned=False, lexical_weight=0.5,
    )
    assert recs[0].issue_id == 1  # the exact-title issue wins


def test_search_finds_closed_issues_unless_only_unclaimed(session):
    # The bug: a closed tracker was invisible to search (snapshot was open-only).
    from app.ai.embedder import get_embedder
    from app.services.recommendations import recommend_issues, resolve_query_vector

    _issue(session, 1, "Measure BlueStore caches performance", "measure bluestore cache perf",
           is_open=False)  # the exact-title issue is closed
    _issue(session, 2, "Memory recommendations for bluestore", "bluestore memory")
    session.commit()
    refresh_embeddings(session)

    qvec, excl, text = resolve_query_vector(
        session, "Measure BlueStore caches performance", get_embedder()
    )
    # Default search reaches closed issues.
    recs = recommend_issues(
        session, skill_prompt=text, query_vector=qvec, stretch=0,
        exclude_assigned=False, include_closed=True, lexical_weight=0.5,
    )
    assert recs[0].issue_id == 1  # the closed exact-title match is found and #1

    # only_unclaimed == include_closed False -> the closed issue is gone.
    recs2 = recommend_issues(
        session, skill_prompt=text, query_vector=qvec, stretch=0,
        exclude_assigned=True, include_closed=False, lexical_weight=0.5,
    )
    assert all(r.issue_id != 1 for r in recs2)


def test_search_like_tracker_excludes_itself(session):
    from app.ai.embedder import get_embedder
    from app.services.recommendations import recommend_issues, resolve_query_vector

    _issue(session, 77219, "rbd mirror replayer stuck", "replayer snapshot sync hang")
    _issue(session, 77220, "rbd mirror replayer hang", "replayer snapshot sync stuck")
    _issue(session, 77221, "unrelated docs typo", "spelling")
    session.commit()
    refresh_embeddings(session)

    qvec, excl, text = resolve_query_vector(session, "like tracker 77219", get_embedder())
    assert excl == {77219}  # the referenced tracker is flagged for exclusion
    recs = recommend_issues(
        session, skill_prompt=text, query_vector=qvec, stretch=0,
        exclude_assigned=False, exclude_issue_ids=excl,
    )
    ids = {r.issue_id for r in recs}
    assert 77219 not in ids  # never returns the queried tracker itself
    assert 77220 in ids  # the similar tracker surfaces


def test_exclude_linked_hides_pr_and_assigned(session):
    from app.ai.embedder import get_embedder
    from app.models import PullRequest
    from app.services.recommendations import recommend_issues, resolve_query_vector

    _issue(session, 1, "bluestore cache perf free", "bluestore cache")
    _issue(session, 2, "bluestore cache perf assigned", "bluestore cache")
    session.add(
        Issue(id=3, subject="bluestore cache perf linked", description="bluestore cache",
              is_open=True, content_hash=content_hash("3"),
              url="https://tracker.ceph.com/issues/3")
    )
    # #2 gets an assignee; a PR references #3.
    session.add(
        PullRequest(id="P", repo_full_name="ceph/ceph", number=9, state="open",
                    title="x", body="fixes #3", referenced_issue_ids=[3],
                    content_hash=content_hash("p"),
                    url="https://github.com/ceph/ceph/pull/9")
    )
    session.commit()
    session.get(Issue, 2).assignee_login = "jane"
    session.commit()
    refresh_embeddings(session)

    qvec, excl, text = resolve_query_vector(session, "bluestore cache perf", get_embedder())
    recs = recommend_issues(
        session, skill_prompt=text, query_vector=qvec, stretch=0,
        exclude_assigned=True, exclude_linked=True,
    )
    ids = {r.issue_id for r in recs}
    assert ids == {1}  # assigned #2 and PR-linked #3 are hidden


def test_profile_roundtrip_and_empty_prompt(session):
    profile = get_or_create_profile(session)
    assert profile.external_id == "me"
    # No prompt -> no recommendations, no crash.
    assert recommend_issues(session, skill_prompt="  ") == []
