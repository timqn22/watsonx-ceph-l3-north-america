"""HTTP API routes.

Thin controllers: they validate input, call the service/repository layer, and
return pydantic schemas. Read endpoints for the extension, plus an admin
rescrape hook for live demos.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ai.embedder import get_embedder
from .ai.linkage import related_prs_for_issue
from .config import get_settings
from .db import get_session
from .models import Issue, LinkSuggestion, PullRequest
from .schemas import (
    DecisionIn,
    HealthOut,
    InProgressOut,
    IssueOut,
    JobInfo,
    LinkSuggestionOut,
    ProfileIn,
    ProfileOut,
    PullRequestOut,
    RecommendationOut,
    RecommendIn,
    RelatedPrOut,
    RescrapeIn,
)
from .scheduler import get_scheduler
from .services.pipeline import run_source
from .services.recommendations import get_or_create_profile, recommend_issues
from .services.work_status import in_progress_issue_ids, in_progress_map

router = APIRouter()

_VALID_DECISIONS = {"accepted", "rejected", "ignored"}
_VALID_SOURCES = {"redmine_open", "redmine_closed", "github_open", "github_closed"}


def _enrich(session: Session, s: LinkSuggestion) -> LinkSuggestionOut:
    """Attach PR/issue display fields to a suggestion."""
    pr = session.get(PullRequest, s.pr_id)
    issue = session.get(Issue, s.issue_id)
    return LinkSuggestionOut(
        id=s.id,
        pr_id=s.pr_id,
        issue_id=s.issue_id,
        similarity=round(s.similarity, 4),
        status=s.status,
        model_id=s.model_id,
        created_at=s.created_at,
        pr_number=pr.number if pr else None,
        pr_repo=pr.repo_full_name if pr else None,
        pr_title=pr.title if pr else None,
        pr_url=pr.url if pr else None,
        issue_subject=issue.subject if issue else None,
        issue_url=issue.url if issue else None,
    )


@router.get("/health", response_model=HealthOut)
def health(session: Session = Depends(get_session)) -> HealthOut:
    db_ok = True
    try:
        session.execute(select(func.count()).select_from(Issue))
    except Exception:
        db_ok = False

    scheduler = get_scheduler()
    jobs: list[JobInfo] = []
    if scheduler:
        for job in scheduler.get_jobs():
            jobs.append(
                JobInfo(
                    name=job.id,
                    next_run_time=(
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                )
            )

    return HealthOut(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        embedder=get_embedder().model_id,
        watsonx_configured=get_settings().watsonx_configured,
        issues=session.scalar(select(func.count()).select_from(Issue)) or 0,
        pull_requests=session.scalar(select(func.count()).select_from(PullRequest)) or 0,
        pending_suggestions=session.scalar(
            select(func.count())
            .select_from(LinkSuggestion)
            .where(LinkSuggestion.status == "pending")
        )
        or 0,
        jobs=jobs,
    )


@router.get("/issues", response_model=list[IssueOut])
def list_issues(
    limit: int = Query(50, le=200),
    session: Session = Depends(get_session),
) -> list[Issue]:
    return list(
        session.scalars(
            select(Issue).order_by(Issue.updated_on.desc()).limit(limit)
        )
    )


@router.get("/pulls", response_model=list[PullRequestOut])
def list_pulls(
    limit: int = Query(50, le=200),
    session: Session = Depends(get_session),
) -> list[PullRequest]:
    return list(
        session.scalars(
            select(PullRequest).order_by(PullRequest.updated_at.desc()).limit(limit)
        )
    )


@router.get(
    "/suggestions/links/unlinked", response_model=list[LinkSuggestionOut]
)
def unlinked(
    min_similarity: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, le=200),
    session: Session = Depends(get_session),
) -> list[LinkSuggestionOut]:
    """Manager view: pending suggestions, strongest first."""
    rows = session.scalars(
        select(LinkSuggestion)
        .where(LinkSuggestion.status == "pending")
        .where(LinkSuggestion.similarity >= min_similarity)
        .order_by(LinkSuggestion.similarity.desc())
        .limit(limit)
    )
    return [_enrich(session, s) for s in rows]


@router.get(
    "/suggestions/links/for-issue/{issue_id}",
    response_model=list[LinkSuggestionOut],
)
def for_issue(
    issue_id: int, session: Session = Depends(get_session)
) -> list[LinkSuggestionOut]:
    rows = session.scalars(
        select(LinkSuggestion)
        .where(LinkSuggestion.issue_id == issue_id)
        .where(LinkSuggestion.status.in_(("pending", "accepted")))
        .order_by(LinkSuggestion.similarity.desc())
    )
    return [_enrich(session, s) for s in rows]


@router.get(
    "/suggestions/links/for-pr/{pr_id}", response_model=list[LinkSuggestionOut]
)
def for_pr(
    pr_id: str, session: Session = Depends(get_session)
) -> list[LinkSuggestionOut]:
    rows = session.scalars(
        select(LinkSuggestion)
        .where(LinkSuggestion.pr_id == pr_id)
        .where(LinkSuggestion.status.in_(("pending", "accepted")))
        .order_by(LinkSuggestion.similarity.desc())
    )
    return [_enrich(session, s) for s in rows]


@router.post(
    "/suggestions/links/{suggestion_id}/decision",
    response_model=LinkSuggestionOut,
)
def decide(
    suggestion_id: int,
    body: DecisionIn,
    session: Session = Depends(get_session),
) -> LinkSuggestionOut:
    if body.status not in _VALID_DECISIONS:
        raise HTTPException(422, f"status must be one of {sorted(_VALID_DECISIONS)}")
    s = session.get(LinkSuggestion, suggestion_id)
    if s is None:
        raise HTTPException(404, "suggestion not found")
    s.status = body.status
    s.decided_at = datetime.now(timezone.utc)
    s.decided_by = body.decided_by
    session.commit()
    return _enrich(session, s)


def _apply_profile(profile, body: ProfileIn) -> None:
    profile.skill_prompt = body.skill_prompt
    profile.background = body.background
    profile.display_name = body.display_name
    profile.preferred_projects = body.preferred_projects
    profile.preferred_trackers = body.preferred_trackers
    profile.preferred_priorities = body.preferred_priorities
    # Invalidate the cached embedding; recomputed on next recommendation.
    profile.skill_embedding = None
    profile.skill_embedded_hash = None


@router.get("/profiles/me", response_model=ProfileOut)
def get_profile(session: Session = Depends(get_session)) -> ProfileOut:
    return ProfileOut.model_validate(get_or_create_profile(session))


@router.get("/profiles/{external_id}", response_model=ProfileOut)
def get_profile_by_id(
    external_id: str, session: Session = Depends(get_session)
) -> ProfileOut:
    return ProfileOut.model_validate(get_or_create_profile(session, external_id))


@router.put("/profiles/me", response_model=ProfileOut)
def put_profile(
    body: ProfileIn, session: Session = Depends(get_session)
) -> ProfileOut:
    profile = get_or_create_profile(session)
    _apply_profile(profile, body)
    session.commit()
    return ProfileOut.model_validate(profile)


@router.put("/profiles/{external_id}", response_model=ProfileOut)
def put_profile_by_id(
    external_id: str, body: ProfileIn, session: Session = Depends(get_session)
) -> ProfileOut:
    profile = get_or_create_profile(session, external_id)
    _apply_profile(profile, body)
    session.commit()
    return ProfileOut.model_validate(profile)


def _effective_prompt(skill: str, background: str | None) -> str:
    return "\n\n".join(p for p in (skill, background) if p and p.strip()).strip()


@router.post("/recommendations/issues", response_model=list[RecommendationOut])
def recommend(
    body: RecommendIn, session: Session = Depends(get_session)
) -> list[RecommendationOut]:
    profile = get_or_create_profile(session, body.user or "me")
    if body.skill_prompt is not None:
        skill_prompt = body.skill_prompt
    else:
        # Fold the saved background/previous-projects into the skill text.
        skill_prompt = _effective_prompt(profile.skill_prompt, profile.background)
    if not skill_prompt.strip():
        raise HTTPException(422, "No skill_prompt provided and no profile saved yet")

    exclude = None if body.include_in_progress else in_progress_issue_ids(session)
    recs = recommend_issues(
        session,
        skill_prompt=skill_prompt,
        projects=body.projects or profile.preferred_projects,
        trackers=body.trackers or profile.preferred_trackers,
        priorities=body.priorities or profile.preferred_priorities,
        limit=body.limit,
        exclude_issue_ids=exclude,
    )

    out: list[RecommendationOut] = []
    for r in recs:
        issue = session.get(Issue, r.issue_id)
        out.append(
            RecommendationOut(
                issue_id=r.issue_id,
                fit_score=r.fit_score,
                similarity=round(r.similarity, 4),
                reason=r.reason,
                is_stretch=r.is_stretch,
                subject=issue.subject if issue else None,
                tracker_name=issue.tracker_name if issue else None,
                priority=issue.priority if issue else None,
                project_name=issue.project_name if issue else None,
                url=issue.url if issue else None,
            )
        )
    return out


@router.get("/issues/{issue_id}/related-prs", response_model=list[RelatedPrOut])
def related_prs(
    issue_id: int, session: Session = Depends(get_session)
) -> list[RelatedPrOut]:
    """All PRs related to an issue: already-linked ones plus likely matches,
    across open/merged/closed — for the extension's issue-page panel."""
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(404, "issue not found")
    out: list[RelatedPrOut] = []
    for r in related_prs_for_issue(session, issue):
        out.append(
            RelatedPrOut(
                relationship=r.relationship,
                similarity=round(r.similarity, 4) if r.similarity is not None else None,
                confidence=round(r.confidence, 4) if r.confidence is not None else None,
                pr_number=r.pr.number,
                pr_repo=r.pr.repo_full_name,
                pr_title=r.pr.title,
                pr_url=r.pr.url,
                state=r.pr.state,
            )
        )
    return out


@router.get("/issues/in-progress", response_model=list[InProgressOut])
def issues_in_progress(
    unassigned_only: bool = Query(False),
    limit: int = Query(100, le=500),
    session: Session = Depends(get_session),
) -> list[InProgressOut]:
    """Open issues that already have a PR working on them.

    Set ``unassigned_only=true`` to catch the real pain: work started without
    anyone assigning the tracker to themselves.
    """
    evidence = in_progress_map(session)
    out: list[InProgressOut] = []
    for issue_id, ev in evidence.items():
        issue = session.get(Issue, issue_id)
        if issue is None:
            continue
        unassigned = not issue.assignee_login
        if unassigned_only and not unassigned:
            continue
        out.append(
            InProgressOut(
                issue_id=issue_id,
                subject=issue.subject,
                issue_url=issue.url,
                assignee_login=issue.assignee_login,
                is_unassigned=unassigned,
                evidence=ev.kind,
                similarity=round(ev.similarity, 4) if ev.similarity is not None else None,
                pr_number=ev.pr.number,
                pr_repo=ev.pr.repo_full_name,
                pr_title=ev.pr.title,
                pr_url=ev.pr.url,
            )
        )
    # Unassigned first, then referenced (definite) before matches, then by score.
    out.sort(
        key=lambda r: (
            not r.is_unassigned,
            r.evidence != "referenced",
            -(r.similarity or 1.0),
        )
    )
    return out[:limit]


@router.post("/admin/rescrape")
def rescrape(body: RescrapeIn, background: BackgroundTasks) -> dict[str, str]:
    if body.source not in _VALID_SOURCES:
        raise HTTPException(422, f"source must be one of {sorted(_VALID_SOURCES)}")
    background.add_task(run_source, body.source)
    return {"status": "scheduled", "source": body.source}
