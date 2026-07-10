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


def test_profile_roundtrip_and_empty_prompt(session):
    profile = get_or_create_profile(session)
    assert profile.external_id == "me"
    # No prompt -> no recommendations, no crash.
    assert recommend_issues(session, skill_prompt="  ") == []
