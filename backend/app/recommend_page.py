"""Browser page for Feature B: personalized task recommendations.

A self-contained page (no deps) with a skill-description box and filters. It
POSTs to /recommendations/issues and renders ranked issue cards with a fit
score, the matched project/tracker/priority, and a short "why". Mirrors the
dashboard's look.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TrackerAssist — Recommended Tasks</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
         background:#0f1115; color:#e7e9ee; }
  header { padding:20px 28px; border-bottom:1px solid #262a33; background:#151821; }
  h1 { margin:0; font-size:19px; }
  .meta { color:#9aa2b1; font-size:13px; margin-top:4px; }
  .accent { color:#7cc5ff; }
  main { padding:24px 28px; max-width:920px; margin:0 auto; }
  label { display:block; color:#9aa2b1; font-size:13px; margin:12px 0 4px; }
  textarea, input { width:100%; background:#0f1115; color:#e7e9ee;
    border:1px solid #333a47; border-radius:8px; padding:10px 12px; font:inherit; }
  textarea { min-height:90px; resize:vertical; }
  .row { display:grid; grid-template-columns:1fr 1fr 1fr 120px; gap:12px; }
  button.go { margin-top:16px; background:#22304a; border:1px solid #33507e;
    color:#e7e9ee; border-radius:8px; padding:10px 18px; font-size:14px; cursor:pointer; }
  button.go:hover { background:#2b3d5e; }
  .cards { margin-top:24px; display:flex; flex-direction:column; gap:12px; }
  .card { background:#171a22; border:1px solid #262a33; border-left:3px solid #7cc5ff;
    border-radius:8px; padding:14px 16px; display:flex; gap:16px; align-items:flex-start; }
  .card.stretch { border-left-color:#d9a441; }
  .score { flex:0 0 66px; text-align:center; }
  .score .n { font-size:24px; font-weight:700; }
  .score .l { font-size:11px; color:#6f7788; text-transform:uppercase; }
  .body { flex:1; }
  .body .subj { font-size:15px; }
  .tags { margin-top:5px; display:flex; gap:8px; flex-wrap:wrap; }
  .tag { font-size:11px; color:#9aa2b1; background:#1c2029; border:1px solid #2a2f3a;
    border-radius:12px; padding:2px 9px; }
  .tag.stretch { color:#e8c07a; border-color:#5a4a24; }
  .why { color:#8b93a3; font-size:13px; margin-top:6px; }
  a { color:#7cc5ff; text-decoration:none; }
  .hint { color:#6f7788; font-size:12px; margin-top:4px; }
  .empty { color:#6f7788; padding:20px 0; }
</style>
</head>
<body>
<header>
  <h1>TrackerAssist — Recommended Tasks</h1>
  <div class="meta">Describe your skills; open issues are ranked by fit using
    <span class="accent">Granite</span> embeddings.</div>
</header>
<main>
  <label for="skill">Your skills (free text)</label>
  <textarea id="skill" placeholder="e.g. Strong in C++ and RADOS internals, comfortable with RBD mirroring and CephFS, newer to Kubernetes and cephadm..."></textarea>
  <div class="hint">The more specific, the better the match.</div>

  <div class="row">
    <div><label for="projects">Projects (optional)</label>
      <input id="projects" placeholder="RBD, CephFS"></div>
    <div><label for="trackers">Trackers (optional)</label>
      <input id="trackers" placeholder="Bug, Feature"></div>
    <div><label for="priorities">Priorities (optional)</label>
      <input id="priorities" placeholder="High, Urgent"></div>
    <div><label for="limit">How many</label>
      <input id="limit" type="number" min="1" max="50" value="12"></div>
  </div>
  <div class="hint">Comma-separated. Leave blank to search all.</div>

  <button class="go" onclick="recommend()">Find tasks for me</button>

  <div class="cards" id="cards"></div>
</main>
<script>
function list(id) {
  return document.getElementById(id).value.split(',').map(s => s.trim()).filter(Boolean);
}
async function recommend() {
  const cards = document.getElementById('cards');
  cards.innerHTML = '<div class="empty">Ranking issues…</div>';
  const body = {
    skill_prompt: document.getElementById('skill').value,
    projects: list('projects'), trackers: list('trackers'),
    priorities: list('priorities'),
    limit: parseInt(document.getElementById('limit').value || '12', 10)
  };
  try {
    const r = await fetch('/recommendations/issues', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (!r.ok) { cards.innerHTML = '<div class="empty">' +
      (r.status === 422 ? 'Please describe your skills first.' : 'Error ' + r.status) +
      '</div>'; return; }
    const data = await r.json();
    if (!data.length) { cards.innerHTML =
      '<div class="empty">No matching open issues. Try broadening filters.</div>'; return; }
    cards.innerHTML = data.map(function(d) {
      const stretch = d.is_stretch ? ' stretch' : '';
      const stretchTag = d.is_stretch ? '<span class="tag stretch">stretch pick</span>' : '';
      const tags = [d.project_name, d.tracker_name, d.priority]
        .filter(Boolean).map(t => '<span class="tag">' + t + '</span>').join('');
      return '<div class="card' + stretch + '">' +
        '<div class="score"><div class="n">' + d.fit_score + '</div>' +
        '<div class="l">fit</div></div>' +
        '<div class="body"><div class="subj"><a href="' + (d.url||'#') +
        '" target="_blank">#' + d.issue_id + '</a> ' + escapeHtml(d.subject||'') + '</div>' +
        '<div class="tags">' + tags + stretchTag + '</div>' +
        '<div class="why">' + escapeHtml(d.reason||'') + '</div></div></div>';
    }).join('');
  } catch (e) { cards.innerHTML = '<div class="empty">Request failed: ' + e + '</div>'; }
}
function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}
document.getElementById('skill').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) recommend();
});
</script>
</body>
</html>"""


@router.get("/recommend", response_class=HTMLResponse)
def recommend_page() -> HTMLResponse:
    return HTMLResponse(_PAGE)
