"""Cross-encoder reranking reorders candidates (with a stub, no model download)."""

from __future__ import annotations

from app.ai.linkage import related_prs_for_issue
from app.models import Issue, PullRequest
from app.services.indexer import refresh_embeddings
from app.services.recommendations import recommend_issues
from app.text import content_hash


class StubReranker:
    """Prefers docs containing the word 'winner'."""

    enabled = True
    model_id = "stub"

    def scores(self, query, docs):
        return [0.95 if "winner" in d.lower() else 0.05 for d in docs]


def _issue(session, id_, subject, desc, **kw):
    session.add(Issue(id=id_, subject=subject, description=desc, is_open=True,
                      content_hash=content_hash(subject, desc),
                      url=f"https://tracker.ceph.com/issues/{id_}", **kw))


def _pr(session, id_, num, title, body):
    session.add(PullRequest(id=id_, repo_full_name="ceph/ceph", number=num, state="open",
                            title=title, body=body, referenced_issue_ids=[],
                            content_hash=content_hash(title, body),
                            url=f"https://github.com/ceph/ceph/pull/{num}"))


def test_reranker_reorders_related_prs(session):
    _issue(session, 1, "rbd mirror snapshot replayer", "sync work")
    # PR_A is the stronger embedding match; PR_B is what the cross-encoder prefers.
    _pr(session, "A", 10, "rbd mirror snapshot replayer", "sync work")
    _pr(session, "B", 11, "rbd mirror snapshot replayer", "the winner fix")
    session.commit()
    refresh_embeddings(session)

    rel = related_prs_for_issue(
        session, session.get(Issue, 1), reranker=StubReranker()
    )
    assert rel[0].pr.number == 11  # reranked to the top
    assert abs(rel[0].confidence - 0.95) < 1e-6  # confidence = reranker relevance


def test_reranker_reorders_recommendations(session):
    _issue(session, 1, "generic ceph work", "do a thing")
    _issue(session, 2, "generic ceph work winner", "do a thing")
    session.commit()
    refresh_embeddings(session)

    recs = recommend_issues(
        session, skill_prompt="generic ceph work", stretch=0,
        reranker=StubReranker(),
    )
    assert recs[0].issue_id == 2
    assert recs[0].fit_score == 100  # fit is relative: the best reranked pick tops out
