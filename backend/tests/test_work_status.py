"""In-progress detection: an issue already has a PR working on it."""

from __future__ import annotations

from app.models import Issue, PullRequest
from app.services.indexer import refresh_embeddings
from app.services.recommendations import recommend_issues
from app.services.work_status import in_progress_issue_ids, in_progress_map
from app.text import content_hash


def _issue(session, id_, subject, desc, *, assignee=None, is_open=True):
    session.add(
        Issue(id=id_, subject=subject, description=desc, is_open=is_open,
              assignee_login=assignee, content_hash=content_hash(subject, desc),
              url=f"https://tracker.ceph.com/issues/{id_}")
    )


def _pr(session, id_, num, title, body, referenced=None, state="open"):
    session.add(
        PullRequest(id=id_, repo_full_name="ceph/ceph", number=num, state=state,
                    title=title, body=body, referenced_issue_ids=referenced or [],
                    content_hash=content_hash(title, body),
                    url=f"https://github.com/ceph/ceph/pull/{num}")
    )


def test_referenced_pr_marks_issue_in_progress(session):
    _issue(session, 1, "rbd mirror snapshot bug", "replayer stuck")
    _pr(session, "PR_1", 10, "fix rbd mirror", "work", referenced=[1])
    session.commit()
    refresh_embeddings(session)

    ev = in_progress_map(session)
    assert 1 in ev and ev[1].kind == "referenced"
    assert ev[1].pr.number == 10


def test_high_similarity_pr_marks_issue_in_progress(session):
    _issue(session, 1, "rbd mirror snapshot replayer stuck on boot",
           "the rbd-mirror image replayer hangs during snapshot sync on startup")
    # Nearly identical text, but no reference -> should be caught as a match.
    _pr(session, "PR_1", 10, "rbd mirror snapshot replayer stuck on boot",
        "the rbd-mirror image replayer hangs during snapshot sync on startup")
    session.commit()
    refresh_embeddings(session)

    ev = in_progress_map(session, min_similarity=0.9)
    assert 1 in ev and ev[1].kind == "match"
    assert ev[1].similarity >= 0.9


def test_recommender_excludes_in_progress(session):
    _issue(session, 1, "rbd mirror snapshot", "rbd mirror work")
    _issue(session, 2, "rbd mirror snapshot other", "rbd mirror work too")
    _pr(session, "PR_1", 10, "x", "y", referenced=[1])  # issue 1 is taken
    session.commit()
    refresh_embeddings(session)

    taken = in_progress_issue_ids(session)
    assert 1 in taken

    recs = recommend_issues(
        session, skill_prompt="rbd mirror snapshot", stretch=0,
        exclude_issue_ids=taken,
    )
    assert all(r.issue_id != 1 for r in recs)  # never recommend taken work
    assert any(r.issue_id == 2 for r in recs)  # the free one is still offered
