// TrackerAssist content script.
// Injects two panels into Redmine pages:
//   * On an issue page (/issues/123): "Related pull requests" — likely PRs to
//     link, with Accept / Ignore.
//   * On issue listings / My page: "Recommended for you" — issues ranked to the
//     signed-in user's profile, with a priority filter dropdown.
// All data comes from the TrackerAssist backend (URL + user id from the popup).

(function () {
  "use strict";

  const PRIORITIES = ["Low", "Normal", "High", "Urgent", "Immediate"];

  function storageGet(keys) {
    return new Promise((res) => chrome.storage.sync.get(keys, res));
  }

  // Tiny DOM builder.
  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    attrs = attrs || {};
    for (const k in attrs) {
      if (k === "class") n.className = attrs[k];
      else if (k === "html") n.innerHTML = attrs[k];
      else if (k.slice(0, 2) === "on")
        n.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    }
    for (const kid of kids) {
      if (kid == null) continue;
      n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return n;
  }

  function mountPanel(title, subtitle, storageKey) {
    const host = document.querySelector("#content") || document.body;
    const panel = el("div", { class: "ta-panel" });
    const chevron = el("span", { class: "ta-chevron" }, "▾"); // ▾
    const header = el(
      "div",
      { class: "ta-head ta-clickable", title: "Click to collapse / expand" },
      chevron,
      el("span", { class: "ta-logo" }, "TrackerAssist"),
      el("span", { class: "ta-title" }, title)
    );
    // Everything collapsible lives in one wrapper so the header stays visible.
    const wrap = el("div", { class: "ta-wrap" });
    const subEl = el("div", { class: "ta-sub" }, subtitle || "");
    if (subtitle) wrap.append(subEl);
    const bodyEl = el("div", { class: "ta-body" });
    wrap.append(bodyEl);
    panel.append(header, wrap);
    // Expose the subtitle so callers can update it once they know what's shown.
    bodyEl.setSubtitle = (text) => {
      subEl.textContent = text || "";
      if (text && !subEl.parentNode) wrap.insertBefore(subEl, bodyEl);
    };

    const setCollapsed = (c) => {
      panel.classList.toggle("ta-collapsed", c);
      chevron.textContent = c ? "▸" : "▾"; // ▸ / ▾
    };
    header.addEventListener("click", () => {
      const c = !panel.classList.contains("ta-collapsed");
      setCollapsed(c);
      if (storageKey) chrome.storage.sync.set({ [storageKey]: c });
    });
    if (storageKey) {
      chrome.storage.sync.get([storageKey], (r) => setCollapsed(!!r[storageKey]));
    }

    host.insertBefore(panel, host.firstChild);
    return bodyEl;
  }

  function banner(bodyEl, msg) {
    bodyEl.replaceChildren(el("div", { class: "ta-note" }, msg));
  }

  function pct(sim) {
    return Math.round((sim || 0) * 100);
  }

  // Fetch with a timeout and a couple of retries for transient failures. The
  // first request after the backend starts builds the (60k-issue) snapshot, so
  // it can be slow or briefly 5xx -- retrying avoids a false "Backend offline".
  // Definitive client errors (4xx, e.g. 422 no-profile) fail immediately.
  async function api(base, path, opts, { retries = 2, timeoutMs = 25000 } = {}) {
    let lastErr;
    for (let attempt = 0; attempt <= retries; attempt++) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeoutMs);
      try {
        const r = await fetch(base + path, { ...opts, signal: ctrl.signal });
        clearTimeout(timer);
        if (r.ok) return r.json();
        if (r.status >= 400 && r.status < 500) throw new Error("HTTP " + r.status);
        lastErr = new Error("HTTP " + r.status); // 5xx -> retry
      } catch (e) {
        clearTimeout(timer);
        if (e && typeof e.message === "string" && e.message.startsWith("HTTP 4")) {
          throw e; // definitive client error -> don't retry
        }
        lastErr = e; // network error / timeout / 5xx -> retry
      }
      if (attempt < retries) {
        await new Promise((res) => setTimeout(res, 600 * (attempt + 1)));
      }
    }
    throw lastErr;
  }

  // ---- Issue page: related pull requests -------------------------------
  // Possible-duplicate warning: renders only when the backend flags trackers
  // above the high-precision duplicate bar, so it stays quiet almost always.
  function renderDuplicates(dupBox, dups) {
    if (!dups || !dups.length) return;
    const list = el("div", { class: "ta-duplist" });
    for (const d of dups) {
      list.append(
        el(
          "div",
          { class: "ta-duprow" },
          el(
            "a",
            { href: d.url || "#", target: "_blank", class: "ta-link" },
            `#${d.issue_id} ${d.subject || ""}`
          ),
          el(
            "span",
            { class: "ta-tag" },
            d.is_open ? (d.status || "open") : (d.status || "closed")
          ),
          el("span", { class: "ta-dupsim" }, `${pct(d.confidence)}% similar`)
        )
      );
    }
    dupBox.replaceChildren(
      el(
        "div",
        { class: "ta-dupbox" },
        el(
          "div",
          { class: "ta-duphead" },
          "⚠ Possible duplicate — a very similar tracker already exists:"
        ),
        list
      )
    );
  }

  async function issuePanel(base, issueId) {
    const body = mountPanel(
      "Related pull requests",
      "Checking for related pull requests…",
      "collapsed_related"
    );
    const dupBox = el("div");
    const prList = el("div");
    body.append(dupBox, prList);
    banner(prList, "Loading…");
    // Duplicate check runs in parallel and renders independently, so it shows
    // even when there are no related PRs (and vice versa).
    api(base, `/issues/${issueId}/similar`)
      .then((dups) => renderDuplicates(dupBox, dups))
      .catch(() => {});
    // Scan only the structured fields (description + custom-field table) for
    // GitHub PR links. Comments are intentionally excluded: a PR mentioned in
    // a comment as a "related" or "helpful" reference is not a formal link and
    // would be incorrectly surfaced as "Linked" in the panel.
    const prNums = new Set();
    const structuredZones = [
      ...document.querySelectorAll("#issue_description, #attributes"),
    ];
    structuredZones.forEach((zone) => {
      zone.querySelectorAll('a[href*="/pull/"]').forEach((a) => {
        const m = (a.getAttribute("href") || "").match(/\/pull\/(\d+)/);
        if (m) prNums.add(m[1]);
      });
    });
    const q = prNums.size ? `?pr_numbers=${[...prNums].join(",")}` : "";
    let items;
    try {
      items = await api(base, `/issues/${issueId}/related-prs${q}`);
    } catch (e) {
      return banner(prList, "Backend offline — check the TrackerAssist popup.");
    }
    if (!items.length) {
      body.setSubtitle("No linked or matching pull requests found for this tracker.");
      return banner(
        prList,
        "No related pull requests in the scraped data. If the PR is merged, " +
          "it may not be synced yet (closed PRs sync every 6h)."
      );
    }
    // Describe what's actually shown, so we never claim "linked" when these are
    // only likely matches.
    const hasLinked = items.some((r) => r.relationship === "linked");
    const hasSuggested = items.some((r) => r.relationship === "suggested");
    body.setSubtitle(
      hasLinked
        ? hasSuggested
          ? "Pull requests linked to this tracker, plus likely matches."
          : "Pull requests linked to this tracker."
        : "Likely matching pull requests — none are linked to this tracker yet."
    );
    prList.replaceChildren();
    for (const s of items) {
      const linked = s.relationship === "linked";
      const conf = pct(s.confidence != null ? s.confidence : s.similarity);
      const left = linked
        ? el("div", { class: "ta-relbadge ta-linked" }, "Linked")
        : el(
            "div",
            { class: "ta-sim" },
            el("div", { class: "ta-bar" }, el("span", { style: `width:${conf}%` })),
            el("div", { class: "ta-simn" }, `${conf}% confidence`)
          );
      const tags = el(
        "div",
        { class: "ta-tags" },
        el("span", { class: "ta-tag" }, s.state)
      );
      // Linked from the tracker only -> the PR never referenced this issue.
      if (linked && s.link_direction === "tracker") {
        tags.append(
          el(
            "span",
            { class: "ta-tag ta-warn", title: "The tracker links this PR, but the PR body has no 'Fixes:' reference back." },
            "⚠ PR not linked back"
          )
        );
      }
      // Two-hop suggestion: this PR is the recorded fix of a similar tracker.
      if (!linked && s.via_issue_id) {
        tags.append(
          el(
            "a",
            {
              class: "ta-tag ta-via",
              href: `${location.origin}/issues/${s.via_issue_id}`,
              target: "_blank",
              title: s.via_issue_subject || "",
            },
            `via similar tracker #${s.via_issue_id}`
          )
        );
      }
      prList.append(
        el(
          "div",
          { class: "ta-card" },
          left,
          el(
            "div",
            { class: "ta-info" },
            el(
              "a",
              { href: s.pr_url || "#", target: "_blank", class: "ta-link" },
              `${s.pr_repo} #${s.pr_number}`
            ),
            el("div", { class: "ta-desc" }, s.pr_title || ""),
            tags
          )
        )
      );
    }
  }

  // Identify the logged-in Redmine user from the page (for auto sign-in).
  function currentRedmineUser() {
    const a =
      document.querySelector('#loggedas a[href*="/users/"]') ||
      document.querySelector('a.user.active[href*="/users/"]');
    if (a) {
      const m = a.getAttribute("href").match(/\/users\/(\d+)/);
      if (m) return { id: parseInt(m[1], 10), login: (a.textContent || "").trim() };
    }
    return null;
  }

  // Build a skill/background text from the user's own Redmine activity, so they
  // never have to type it. Uses public issues.json filtered to them.
  async function redmineActivity(origin, userId) {
    const q = (field) =>
      fetch(
        `${origin}/issues.json?${field}=${userId}&status_id=*&sort=updated_on:desc&limit=50`,
        { credentials: "include" }
      )
        .then((r) => (r.ok ? r.json() : { issues: [] }))
        .catch(() => ({ issues: [] }));
    const [assigned, authored] = await Promise.all([
      q("assigned_to_id"),
      q("author_id"),
    ]);
    const byId = {};
    for (const i of [...(assigned.issues || []), ...(authored.issues || [])])
      byId[i.id] = i;
    const issues = Object.values(byId);
    const subjects = issues.slice(0, 30).map((i) => i.subject).filter(Boolean);
    const projects = [
      ...new Set(issues.map((i) => i.project && i.project.name).filter(Boolean)),
    ];
    const trackers = [
      ...new Set(issues.map((i) => i.tracker && i.tracker.name).filter(Boolean)),
    ];
    const text = subjects.length
      ? `Based on my Ceph tracker history I have worked on: ${subjects.join("; ")}. ` +
        `Main projects: ${projects.join(", ")}. Work types: ${trackers.join(", ")}.`
      : "";
    return { text, projects, trackers, count: issues.length };
  }

  // A reusable multi-select checkbox dropdown. `loadOptions` is an async fn
  // returning [{value, label}]; used for priority, projects, and trackers.
  // One document-level listener (installed once) closes any open filter dropdown
  // when the user clicks outside it — clicks inside (on a checkbox) keep it open.
  function installFilterAutoClose() {
    if (document.__taFilterAutoClose) return;
    document.__taFilterAutoClose = true;
    document.addEventListener("click", (e) => {
      document.querySelectorAll("details.ta-projfilter[open]").forEach((d) => {
        if (!d.contains(e.target)) d.open = false;
      });
    });
  }

  function buildMultiFilter(labelText, loadOptions, onChange) {
    installFilterAutoClose();
    const details = el("details", { class: "ta-projfilter" });
    const summary = el("summary", { class: "ta-projsummary" }, labelText);
    const list = el(
      "div",
      { class: "ta-projlist" },
      el("div", { class: "ta-note" }, "Loading…")
    );
    details.append(summary, list);
    // Opening this filter collapses any other open filter (accordion behavior).
    details.addEventListener("toggle", () => {
      if (!details.open) return;
      document.querySelectorAll("details.ta-projfilter[open]").forEach((d) => {
        if (d !== details) d.open = false;
      });
    });
    const boxes = [];
    const refreshSummary = () => {
      const n = boxes.filter((b) => b.checked).length;
      summary.textContent = n ? `${labelText}: ${n}` : labelText;
    };
    (async () => {
      let opts = [];
      try {
        opts = await loadOptions();
      } catch (e) {
        /* leave empty */
      }
      if (!opts.length) {
        return list.replaceChildren(el("div", { class: "ta-note" }, "None available"));
      }
      list.replaceChildren(
        ...opts.map((o) => {
          const cb = el("input", { type: "checkbox", value: o.value });
          cb.addEventListener("change", () => {
            refreshSummary();
            onChange();
          });
          boxes.push(cb);
          return el("label", { class: "ta-projitem" }, cb, ` ${o.label}`);
        })
      );
    })();
    return {
      element: details,
      selected: () => boxes.filter((b) => b.checked).map((b) => b.value),
    };
  }

  // ---- Listing / My page: recommendations ------------------------------
  async function recommendPanel(base, settingsUser) {
    const body = mountPanel(
      "Recommended for you",
      "Open issues ranked to your profile. Claimed work (PR or assignee) is hidden — untick “hide claimed” to show it (tagged).",
      "collapsed_recommend"
    );

    const rUser = currentRedmineUser();
    const user = settingsUser || (rUser && rUser.login) || "";
    if (!user) {
      return banner(
        body,
        "Couldn't detect your Redmine login. Open the TrackerAssist popup and set your ID."
      );
    }

    // Ensure the user has a profile; if not, auto-build one from their Redmine
    // activity and save it so it persists (and powers the dashboard too).
    async function ensureProfile(force) {
      let profile = null;
      try {
        profile = await api(base, `/profiles/${encodeURIComponent(user)}`);
      } catch (e) {
        return { mode: "offline" };
      }
      const hasContent =
        profile &&
        ((profile.skill_prompt || "").trim() || (profile.background || "").trim());
      if (hasContent && !force) return { mode: "profile" };
      if (!rUser) return { mode: hasContent ? "profile" : "none" };
      const act = await redmineActivity(location.origin, rUser.id);
      if (!act.text) return { mode: hasContent ? "profile" : "none" };
      try {
        await api(base, `/profiles/${encodeURIComponent(user)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            skill_prompt: force ? "" : profile.skill_prompt || "",
            background: act.text,
            display_name: rUser.login,
            preferred_projects: act.projects,
            preferred_trackers: act.trackers,
            preferred_priorities: null,
          }),
        });
      } catch (e) {
        /* still recommend below using the derived text if save failed */
      }
      return { mode: "auto", count: act.count };
    }

    // Source note (how the profile was built) + filter row. All three filters
    // are multi-select; leaving one empty falls back to your saved areas.
    const note = el("div", { class: "ta-source" }, `Signed in as ${user}.`);
    const onFilterChange = () => load(false);
    const priorityFilter = buildMultiFilter(
      "Priority",
      async () => PRIORITIES.map((p) => ({ value: p, label: p })),
      onFilterChange
    );
    const projectFilter = buildMultiFilter(
      "Projects",
      async () =>
        (await api(base, "/projects")).map((p) => ({
          value: p.name,
          label: `${p.name} (${p.open_issues})`,
        })),
      onFilterChange
    );
    const trackerFilter = buildMultiFilter(
      "Trackers",
      async () =>
        (await api(base, "/trackers")).map((t) => ({
          value: t.name,
          label: `${t.name} (${t.open_issues})`,
        })),
      onFilterChange
    );
    const refresh = el("button", { class: "ta-refresh" }, "Refresh");
    const rederive = el("a", { class: "ta-relink", href: "#" }, "Rebuild from my activity");
    const controls = el(
      "div",
      { class: "ta-controls" },
      el("label", {}, "Filters"),
      priorityFilter.element,
      projectFilter.element,
      trackerFilter.element,
      refresh,
      rederive
    );
    // Search box: free text and/or "tracker NNNNN". Works alongside the filters.
    const search = el("input", {
      class: "ta-search",
      type: "search",
      placeholder: 'Search — e.g. "performance counters for bluestore" or "like tracker 77219"',
    });
    // Search finds anything (any state, claimed or not); this narrows to open,
    // unassigned, not-in-progress work.
    const unclaimed = el("input", { type: "checkbox", class: "ta-check" });
    const unclaimedLabel = el(
      "label",
      { class: "ta-checklabel", title: "Hide issues that already have a linked PR or an assignee" },
      unclaimed,
      " hide claimed"
    );
    const searchRow = el("div", { class: "ta-searchrow" }, search, unclaimedLabel);
    // Restore the saved preference; default ON so recommendations are curated
    // (claimed work hidden) out of the box. Untick to reveal claimed trackers.
    const savedHide = (await storageGet(["hideClaimed"])).hideClaimed;
    unclaimed.checked = savedHide === undefined ? true : !!savedHide;
    const results = el("div", { class: "ta-results" });
    body.append(note, searchRow, controls, results);

    function describeMode(m) {
      if (m.mode === "auto")
        note.textContent = `Signed in as ${user} · personalized from your ${m.count} recent Ceph trackers (refine in the popup).`;
      else if (m.mode === "profile")
        note.textContent = `Signed in as ${user} · using your saved profile.`;
      else if (m.mode === "none")
        note.textContent = `Signed in as ${user} · no skills yet — add them in the popup, or nothing was found in your Redmine activity.`;
      else note.textContent = `Signed in as ${user}.`;
    }

    function renderRecs(recs) {
      results.replaceChildren();
      for (const d of recs) {
        const tags = el("div", { class: "ta-tags" });
        for (const t of [d.project_name, d.tracker_name, d.priority]) {
          if (t) tags.append(el("span", { class: "ta-tag" }, t));
        }
        if (d.is_stretch) tags.append(el("span", { class: "ta-tag ta-stretch" }, "stretch pick"));
        // Claim status: warn when this isn't actually free work.
        if (d.has_linked_pr)
          tags.append(el("span", { class: "ta-tag ta-claimed" }, "PR linked"));
        if (d.assignee)
          tags.append(el("span", { class: "ta-tag ta-claimed" }, `assigned: ${d.assignee}`));
        results.append(
          el(
            "div",
            { class: "ta-card" + (d.is_stretch ? " ta-card-stretch" : "") },
            el(
              "div",
              { class: "ta-score" },
              el("div", { class: "ta-scoren" }, d.fit_score),
              el("div", { class: "ta-scorel" }, "fit")
            ),
            el(
              "div",
              { class: "ta-info" },
              el(
                "a",
                { href: d.url || "#", target: "_blank", class: "ta-link" },
                `#${d.issue_id} ${d.subject || ""}`
              ),
              tags,
              el("div", { class: "ta-why" }, d.reason || "")
            )
          )
        );
      }
    }

    const load = async (force) => {
      // Empty selection -> null, so the backend narrows to your saved areas by
      // default. A non-empty selection scopes the ranking to those values.
      const orNull = (a) => (a.length ? a : null);
      const priorities = orNull(priorityFilter.selected());
      const projects = orNull(projectFilter.selected());
      const trackers = orNull(trackerFilter.selected());
      const query = (search.value || "").trim();

      // Search mode: rank by the typed query instead of the profile. No profile
      // needed, and the same filters still apply.
      if (query) {
        note.textContent =
          `Search: “${query}”` +
          (priorities || projects || trackers ? " · filtered" : "");
        banner(results, "Searching…");
        let recs;
        try {
          recs = await api(base, "/recommendations/issues", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user, query, priorities, projects, trackers, limit: 12,
              only_unclaimed: unclaimed.checked,
            }),
          });
        } catch (e) {
          return banner(results, "Backend offline — check the TrackerAssist popup.");
        }
        if (!recs.length) return banner(results, "No matching issues for that search.");
        return renderRecs(recs);
      }

      banner(results, force ? "Rebuilding from your activity…" : "Ranking issues…");
      const mode = await ensureProfile(force);
      describeMode(mode);
      if (mode.mode === "none") return banner(results, "");
      banner(results, "Ranking issues…");
      let recs;
      try {
        recs = await api(base, "/recommendations/issues", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user, priorities, projects, trackers, limit: 12,
            only_unclaimed: unclaimed.checked,
          }),
        });
      } catch (e) {
        return banner(
          results,
          e.message.indexOf("422") >= 0
            ? "Your profile has no skills yet — add them in the popup."
            : "Backend offline — check the TrackerAssist popup."
        );
      }
      if (!recs.length) {
        return banner(results, "No matching open issues. Try a different priority.");
      }
      renderRecs(recs);
    };

    // Enter runs the search immediately; typing debounces; clearing the box
    // (the little x, or empty + Enter) falls back to profile recommendations.
    let searchTimer = null;
    search.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        clearTimeout(searchTimer);
        load(false);
      }
    });
    search.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => load(false), 450);
    });
    unclaimed.addEventListener("change", () => {
      chrome.storage.sync.set({ hideClaimed: unclaimed.checked });
      load(false);
    });
    refresh.addEventListener("click", () => load(false));
    rederive.addEventListener("click", (e) => {
      e.preventDefault();
      load(true);
    });
    load(false);
  }

  // ---- Duplicate tracker detection panel ------------------------------
  async function duplicatePanel(base) {
    const body = mountPanel(
      "Duplicate Tracker Detection",
      "Find groups of similar trackers that may be duplicates.",
      "collapsed_duplicates"
    );

    const detectBtn = el("button", { class: "ta-refresh" }, "Generate Duplicate List");
    const status = el("div", { class: "ta-note" }, "");
    const results = el("div", { class: "ta-results" });
    body.append(detectBtn, status, results);

    const load = async () => {
      status.textContent = "Detecting duplicates...";
      results.replaceChildren();
      
      try {
        const groups = await api(base, "/duplicates/detect?min_similarity=0.88&limit=20");
        
        if (!groups || groups.length === 0) {
          status.textContent = "No duplicate groups found.";
          return;
        }
        
        status.textContent = `Found ${groups.length} duplicate group(s)`;
        results.replaceChildren();
        
        for (const [idx, group] of groups.entries()) {
          const groupDiv = el("div", {
            class: "ta-card",
            style: "flex-direction: column; gap: 8px; background: #fdf6e3; border-color: #efd9a8;"
          });
          
          const groupHeader = el("div", {
            style: "font-weight: 600; color: #9a6b12; margin-bottom: 4px;"
          }, `Group ${idx + 1} (${group.group_size} trackers, ${pct(group.max_confidence)}% confidence)`);
          
          groupDiv.append(groupHeader);
          
          for (const [tIdx, tracker] of group.trackers.entries()) {
            const trackerDiv = el("div", {
              style: "margin-left: 12px; padding: 6px; background: #fff; border-radius: 4px; border: 1px solid #e4e8ec;"
            });
            
            const trackerLink = el("a", {
              href: tracker.url || "#",
              target: "_blank",
              class: "ta-link"
            }, `#${tracker.issue_id}: ${tracker.subject || "No subject"}`);
            
            const tags = el("div", { class: "ta-tags", style: "margin-top: 4px;" });
            
            if (tracker.project_name) {
              tags.append(el("span", { class: "ta-tag" }, tracker.project_name));
            }
            if (tracker.tracker_name) {
              tags.append(el("span", { class: "ta-tag" }, tracker.tracker_name));
            }
            if (tracker.status) {
              const statusTag = el("span", {
                class: "ta-tag",
                style: tracker.is_open ? "color: #1a7f37;" : ""
              }, tracker.status);
              tags.append(statusTag);
            }
            if (tIdx > 0) {
              tags.append(el("span", { class: "ta-tag ta-stretch" }, `${pct(tracker.confidence)}% similar`));
            }
            if (tracker.assignee) {
              tags.append(el("span", { class: "ta-tag" }, `Assigned: ${tracker.assignee}`));
            }
            
            trackerDiv.append(trackerLink, tags);
            groupDiv.append(trackerDiv);
          }
          
          results.append(groupDiv);
        }
      } catch (e) {
        status.textContent = "Backend offline — check the TrackerAssist popup.";
        results.replaceChildren();
      }
    };

    detectBtn.addEventListener("click", () => load());
  }

  // ---- Route ----------------------------------------------------------
  (async function main() {
    const cfg = await storageGet(["backendUrl", "userId"]);
    const base = (cfg.backendUrl || "http://localhost:8000").replace(/\/+$/, "");
    const user = cfg.userId || "";
    const path = location.pathname;

    const issue = path.match(/\/issues\/(\d+)/);
    if (issue) {
      issuePanel(base, parseInt(issue[1], 10));
    } else if (
      /\/issues\/?$/.test(path) ||
      /\/my\/page/.test(path) ||
      /\/projects\/[^/]+\/issues/.test(path)
    ) {
      recommendPanel(base, user);
      duplicatePanel(base);
    }
  })();
})();
