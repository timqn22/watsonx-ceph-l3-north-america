"""Manager dashboard: a server-rendered review queue for missing PR<->issue links.

One self-contained HTML page (no templating engine, no JS framework) so it has
zero extra dependencies. It shows coverage stats, scrape health, and the pending
suggestion queue with Accept / Ignore buttons that POST to the existing decision
endpoint. Optionally gated behind ``DASHBOARD_TOKEN``.
"""

from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ai.embedder import get_embedder
from .config import get_settings
from .db import get_session
from .models import Issue, LinkSuggestion, PullRequest, ScrapeState

router = APIRouter()


def _stat_tile(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="sub">{html.escape(sub)}</div>' if sub else ""
    return (
        f'<div class="tile"><div class="num">{html.escape(value)}</div>'
        f'<div class="lbl">{html.escape(label)}</div>{sub_html}</div>'
    )


def _pct(part: int, whole: int) -> str:
    return f"{(100 * part / whole):.0f}%" if whole else "—"


def _coverage(session: Session) -> dict[str, int]:
    open_prs = list(
        session.scalars(select(PullRequest).where(PullRequest.state == "open"))
    )
    referenced = sum(1 for p in open_prs if p.referenced_issue_ids)

    pending_pr_ids = set(
        session.scalars(
            select(LinkSuggestion.pr_id).where(LinkSuggestion.status == "pending")
        )
    )
    accepted_pr_ids = set(
        session.scalars(
            select(LinkSuggestion.pr_id).where(LinkSuggestion.status == "accepted")
        )
    )
    return {
        "open_prs": len(open_prs),
        "referenced": referenced,
        "flagged": len(pending_pr_ids),
        "accepted": len(accepted_pr_ids),
    }


def _suggestion_rows(session: Session, min_similarity: float, limit: int) -> str:
    rows = session.scalars(
        select(LinkSuggestion)
        .where(LinkSuggestion.status == "pending")
        .where(LinkSuggestion.similarity >= min_similarity)
        .order_by(LinkSuggestion.similarity.desc())
        .limit(limit)
    ).all()

    if not rows:
        return (
            '<tr><td colspan="4" class="empty">No pending suggestions above this '
            "threshold. Lower the minimum similarity, or every candidate has been "
            "reviewed.</td></tr>"
        )

    out: list[str] = []
    for s in rows:
        pr = session.get(PullRequest, s.pr_id)
        issue = session.get(Issue, s.issue_id)
        if pr is None or issue is None:
            continue
        pct = int(round(s.similarity * 100))
        out.append(
            f"""<tr id="row-{s.id}">
  <td class="sim">
    <div class="bar"><span style="width:{pct}%"></span></div>
    <div class="simnum">{s.similarity:.3f}</div>
  </td>
  <td>
    <a href="{html.escape(pr.url or '#')}" target="_blank">#{pr.number}</a>
    <span class="repo">{html.escape(pr.repo_full_name)}</span>
    <div class="title">{html.escape(pr.title)}</div>
  </td>
  <td>
    <a href="{html.escape(issue.url or '#')}" target="_blank">#{issue.id}</a>
    <div class="title">{html.escape(issue.subject)}</div>
  </td>
  <td class="actions">
    <button class="ok" onclick="decide({s.id}, 'accepted')">Accept</button>
    <button class="no" onclick="decide({s.id}, 'ignored')">Ignore</button>
  </td>
</tr>"""
        )
    return "\n".join(out)


def _scrape_rows(session: Session) -> str:
    states = session.scalars(select(ScrapeState)).all()
    if not states:
        return '<tr><td colspan="3" class="empty">No scrape has run yet.</td></tr>'
    out = []
    for st in sorted(states, key=lambda x: x.source):
        when = st.last_run_at.strftime("%Y-%m-%d %H:%M UTC") if st.last_run_at else "—"
        status = st.last_status or "—"
        cls = "ok" if status == "ok" else ("no" if status == "error" else "")
        out.append(
            f"<tr><td>{html.escape(st.source)}</td>"
            f'<td class="{cls}">{html.escape(status)}</td>'
            f"<td>{html.escape(when)}</td></tr>"
        )
    return "\n".join(out)


def render_dashboard(
    session: Session, *, min_similarity: float = 0.80, limit: int = 50
) -> str:
    """Build the full dashboard HTML for the current data (pure, testable)."""
    settings = get_settings()
    cov = _coverage(session)
    embedder_id = get_embedder().model_id
    total_pending = (
        session.scalar(
            select(func.count())
            .select_from(LinkSuggestion)
            .where(LinkSuggestion.status == "pending")
        )
        or 0
    )
    src = "watsonx.ai (managed)" if settings.watsonx_configured else "local model"

    tiles = "".join(
        [
            _stat_tile("Open PRs", str(cov["open_prs"])),
            _stat_tile(
                "Already reference a tracker",
                str(cov["referenced"]),
                _pct(cov["referenced"], cov["open_prs"]) + " of open PRs",
            ),
            _stat_tile(
                "Flagged: missing link",
                str(cov["flagged"]),
                f"{total_pending} suggestions",
            ),
            _stat_tile("Accepted links", str(cov["accepted"])),
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TrackerAssist — Manager Dashboard</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
         background:#0f1115; color:#e7e9ee; }}
  header {{ padding:20px 28px; border-bottom:1px solid #262a33;
           background:#151821; }}
  h1 {{ margin:0; font-size:19px; }}
  .meta {{ color:#9aa2b1; font-size:13px; margin-top:4px; }}
  .accent {{ color:#7cc5ff; }}
  main {{ padding:24px 28px; max-width:1100px; margin:0 auto; }}
  .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
           gap:14px; margin-bottom:26px; }}
  .tile {{ background:#171a22; border:1px solid #262a33; border-left:3px solid #7cc5ff;
          border-radius:8px; padding:14px 16px; }}
  .tile .num {{ font-size:26px; font-weight:700; }}
  .tile .lbl {{ color:#9aa2b1; font-size:13px; margin-top:2px; }}
  .tile .sub {{ color:#6f7788; font-size:12px; margin-top:4px; }}
  h2 {{ font-size:15px; color:#c7ccd6; margin:26px 0 10px; }}
  form.filter {{ display:flex; gap:12px; align-items:center; margin-bottom:12px;
                color:#9aa2b1; font-size:13px; }}
  input[type=number] {{ width:80px; background:#0f1115; color:#e7e9ee;
                        border:1px solid #333a47; border-radius:6px; padding:5px 7px; }}
  button.go {{ background:#22304a; }}
  table {{ width:100%; border-collapse:collapse; background:#141721;
          border:1px solid #262a33; border-radius:8px; overflow:hidden; }}
  th,td {{ text-align:left; padding:10px 12px; border-bottom:1px solid #20242e;
          vertical-align:top; }}
  th {{ background:#191d27; color:#9aa2b1; font-size:12px; text-transform:uppercase;
       letter-spacing:.04em; }}
  td .title {{ color:#c2c8d4; font-size:13px; margin-top:3px; }}
  td .repo {{ color:#6f7788; font-size:12px; margin-left:6px; }}
  a {{ color:#7cc5ff; text-decoration:none; }}
  .sim {{ width:120px; }}
  .bar {{ height:7px; background:#232734; border-radius:4px; overflow:hidden; }}
  .bar span {{ display:block; height:100%; background:linear-gradient(90deg,#3a7bd5,#7cc5ff); }}
  .simnum {{ font-size:12px; color:#9aa2b1; margin-top:3px; }}
  .actions {{ width:170px; white-space:nowrap; }}
  button {{ cursor:pointer; border:1px solid #333a47; border-radius:6px;
           padding:6px 12px; font-size:13px; color:#e7e9ee; background:#1c2029; }}
  button.ok:hover {{ background:#1f3a29; border-color:#2f6f47; }}
  button.no:hover {{ background:#3a1f24; border-color:#7a3540; }}
  td.ok, .ok-text {{ color:#5fd18b; }}
  td.no {{ color:#f2889a; }}
  .empty {{ color:#6f7788; text-align:center; padding:22px; }}
  .scrape td {{ font-size:13px; }}
  tr.done {{ opacity:.35; transition:opacity .4s; }}
</style>
</head>
<body>
<header>
  <h1>TrackerAssist — Manager Dashboard</h1>
  <div class="meta">Missing PR ↔ tracker links, ranked by
    <span class="accent">Granite</span> embedding similarity ·
    embeddings via <span class="accent">{html.escape(src)}</span>
    (<span class="accent">{html.escape(embedder_id)}</span>)</div>
</header>
<main>
  <div class="tiles">{tiles}</div>

  <h2>Review queue — likely missing links</h2>
  <form class="filter" method="get" action="/dashboard">
    <label>Min similarity
      <input type="number" name="min_similarity" min="0" max="1" step="0.01"
             value="{min_similarity:.2f}"></label>
    <label>Limit
      <input type="number" name="limit" min="1" max="200" value="{limit}"></label>
    <button class="go" type="submit">Apply</button>
  </form>
  <table>
    <thead><tr><th>Similarity</th><th>Pull request</th><th>Tracker issue</th>
      <th>Decision</th></tr></thead>
    <tbody>{_suggestion_rows(session, min_similarity, limit)}</tbody>
  </table>

  <h2>Scrape health</h2>
  <table class="scrape">
    <thead><tr><th>Source</th><th>Status</th><th>Last run</th></tr></thead>
    <tbody>{_scrape_rows(session)}</tbody>
  </table>
</main>
<script>
async function decide(id, status) {{
  const row = document.getElementById('row-' + id);
  try {{
    const r = await fetch('/suggestions/links/' + id + '/decision', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{status: status, decided_by: 'dashboard'}})
    }});
    if (!r.ok) throw new Error(r.status);
    row.classList.add('done');
    setTimeout(() => row.remove(), 400);
  }} catch (e) {{ alert('Failed to record decision: ' + e); }}
}}
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    min_similarity: float = Query(0.80, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    token: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    configured = get_settings().dashboard_token
    if configured and token != configured:
        raise HTTPException(401, "Missing or invalid ?token= for the dashboard")
    return HTMLResponse(
        render_dashboard(session, min_similarity=min_similarity, limit=limit)
    )
