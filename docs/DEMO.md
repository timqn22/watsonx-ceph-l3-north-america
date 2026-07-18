# TrackerAssist — Demo Script

A presenter walkthrough with the mechanics woven in. Each beat has:
- **[DO]** what to click
- **[SAY]** the narration
- **[HOW IT WORKS]** the mechanism, in case you want to explain it or a judge asks

Total run time: ~4–5 minutes. Everything runs on IBM **Granite** embeddings.

---

## 0. Before you present (prep, ~10 min)

- **Warm the caches.** Restart the backend, let the scrape finish, then open the
  dashboard and one issue page once. The first request after a restart/scrape
  rebuilds an in-memory snapshot of the embeddings; after that every request is
  ~instant. You don't want a judge watching a cold first load.
- **Let the tool pick your best examples** (don't hunt manually):
  ```bash
  # Strongest missing-link pairs — open one of these issues for the linkage beat
  curl -s 'localhost:8000/suggestions/links/unlinked?min_similarity=0.9&limit=5' | python3 -m json.tool
  # Orphaned work — unassigned issues a PR is already tackling (dashboard beat)
  curl -s 'localhost:8000/issues/in-progress?unassigned_only=true&limit=5' | python3 -m json.tool
  ```
  Note 2–3 issue numbers. Keep **#74854** handy as the "Linked via comment/tracker
  + PR not linked back" example.
- Pin the extension and make sure your profile is saved.

---

## 1. The problem (20s)

**[SAY]** "Ceph has around 15,000 open trackers and hundreds of open pull
requests. Two things constantly go wrong. First, a PR fixes a tracker but nobody
links them — so work gets duplicated and managers lose visibility. Second,
contributors don't know what to pick up. TrackerAssist solves both with one
Granite-powered index that sits right on top of Redmine."

**[HOW IT WORKS]** A backend scrapes open Redmine issues and open GitHub PRs on a
15-minute loop (delta-polling the REST APIs, so it only fetches what changed),
stores them in a database, and embeds each one with a Granite model. Everything
below is a query against that shared, always-fresh embedded index.

---

## 2. Linkage — on an issue page (60s)

**[DO]** Open issue **#74854** (a tracker that references its PR).

**[SAY]** "On any issue, TrackerAssist injects a 'Related pull requests' panel.
Here it found the PR and marked it **Linked** — but notice the amber **'PR not
linked back'** flag. The tracker points to the PR, but the PR's description never
referenced the tracker. That's an actionable cleanup: the author should add a
`Fixes:` line so the link shows on GitHub too."

**[HOW IT WORKS]** Links are detected from **both directions**:
- *PR → tracker*: we parse `#1234` and `tracker.ceph.com/issues/1234` URLs out of
  the PR body.
- *tracker → PR*: we parse GitHub PR URLs and the "Pull request ID" field out of
  the issue — **and the extension scans the rendered page, including comments**,
  for PR links, so a PR referenced only in a comment still counts.
A link from either side is "Linked"; when only the tracker side has it, we flag
it. If a real link exists, we show *only* that — no speculative guesses next to a
confirmed link.

**[DO]** Open one of the **no-link** issues you noted in prep.

**[SAY]** "When there's no existing link, it shows **possible matches** — PRs that
look like they belong to this tracker — each with a confidence bar. This isn't
keyword search; Granite understands that a problem description and its fix are
related even when they're worded completely differently."

**[HOW IT WORKS]** Each issue and PR is turned into a vector by the Granite
embedding model (`ibm-granite/granite-embedding-278m-multilingual`), using the
issue's subject+description and the PR's title+body. We rank PRs by **cosine
similarity** to the issue's vector. The percentage is **calibrated**: Granite
scores everything in the Ceph domain around 0.7+ because they share jargon, so we
subtract that baseline — a raw 0.77 shows as a modest, honest confidence rather
than a misleading "77%."

---

## 3. Manager dashboard (45s)

**[DO]** Open `localhost:8000/dashboard`.

**[SAY]** "This is the manager view. Coverage stats up top. The review queue lists
the strongest missing links — accept or ignore each." **[DO]** Click **Accept** on
one; it fades out.

**[SAY]** "And this section is the one people love: **'Unassigned — but already
being worked on.'** Someone started a tracker without assigning it, so it looks
free — but a PR is already in flight. This catches duplicate work *before* it
happens."

**[HOW IT WORKS]** An open issue counts as "in progress" if an open PR references
it (definite) or matches it above a higher confidence bar (cosine ≥ 0.82 — we
require more certainty here than for suggestions). Cross that with "no assignee"
and you get the orphaned-work list. Decisions you make here are remembered, so
the queue reflects live state.

---

## 4. Recommendations (75s)

**[DO]** Go to the issues list (or "My page"). The **"Recommended for you"** panel
is already populated.

**[SAY]** "Here's the second half. Notice I never filled out a profile — it built
one automatically from the trackers I've actually worked on. Each pick has a fit
score and a one-line reason."

**[HOW IT WORKS — profile]** The extension reads your logged-in Redmine identity
from the page, then fetches the issues you've **authored or been assigned** (the
public issues API, in your own session) and builds a short background text —
"worked on: … ; main projects: … ; work types: …" — plus your preferred projects
and tracker types. That's saved server-side under your login. You never type
anything.

**[SAY]** "By default it recommends within my areas. But I can personalize it —"
**[DO]** Open the extension popup. **[SAY]** "— I can add skills or past projects
in free text, or hit 'Rebuild from my activity' to refresh it."

**[HOW IT WORKS — ranking]** Your skills + background text is embedded with the
*same* Granite model into a "profile vector." Open, **unassigned, not-in-progress**
issues are ranked by cosine similarity to that vector; fit score is that
similarity as a percentage. It also mixes in a couple of "stretch" picks — solid
but slightly-outside-your-core issues — to encourage growth.

**[DO]** Check a project and/or a tracker type in the filters. The list re-ranks.

**[SAY]** "The filters are multi-select. The moment I pick something, that becomes
the scope — and the ranking still comes from my profile. With nothing selected it
falls back to my usual areas."

**[HOW IT WORKS — filtering]** This is the important bit: filters are **not**
stacked on top of your profile's saved areas (that used to over-narrow to
nothing). If you select *any* facet, only your selections filter the candidates;
your profile purely drives the *ranking*. With nothing selected, your saved areas
provide the default scope. And it never recommends assigned or already-in-progress
work — only genuinely available issues.

---

## 5. The close — why it's one tool (25s)

**[SAY]** "Both features run on IBM **Granite** embeddings — the same model IBM
serves on watsonx.ai, running locally here so it's free and offline. And they're
one tool, not two, because they share one substrate: a fresh, Granite-embedded
view of every open work item. Linkage compares a PR to issues; recommendations
compare a person to issues. Same math, different anchor — refreshed every 15
minutes."

---

## Quick Q&A cheat-sheet

- **"How does it decide similarity?"** — Granite turns each issue/PR/profile into a
  vector; related things sit close; we rank by cosine similarity. Vectors are
  normalized so cosine is just a dot product.
- **"Why not keyword search?"** — Keywords miss paraphrases. Embeddings catch
  "OSD segfault on boot" ≈ "ceph-osd crashes at startup."
- **"How does the recommender read my profile?"** — It builds one from your own
  Redmine history (authored/assigned issues); you can refine it manually in the
  popup.
- **"Default vs. filtered recommendations?"** — Default = your saved areas, ranked
  by your profile. Pick a filter and that becomes the scope; ranking is still your
  profile.
- **"Is it hammering the tracker?"** — No. Official REST API, delta-polling,
  rate-limit-aware, every 15 minutes.
- **"Where's watsonx?"** — Granite is IBM's model. We run it locally now; the same
  code targets watsonx.ai for managed hosting.
- **"Why is a possible-match confidence only ~30%?"** — Issue text (a problem) and
  PR text (a fix) are inherently a looser match than two issues. Calibrated
  confidence tells the truth: a lead, not a certainty. Thresholds are tunable.

## Don't-do-live list
- No full rescrape (`full=true`) — it's minutes long; scrape beforehand.
- Open each page once first so nothing loads cold.
- Lead with a high-confidence example; use a modest one only to show honesty.
