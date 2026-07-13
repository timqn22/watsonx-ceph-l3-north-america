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

  function mountPanel(title, subtitle) {
    const host = document.querySelector("#content") || document.body;
    const panel = el("div", { class: "ta-panel" });
    const header = el(
      "div",
      { class: "ta-head" },
      el("span", { class: "ta-logo" }, "TrackerAssist"),
      el("span", { class: "ta-title" }, title)
    );
    panel.append(header);
    if (subtitle) panel.append(el("div", { class: "ta-sub" }, subtitle));
    const bodyEl = el("div", { class: "ta-body" });
    panel.append(bodyEl);
    host.insertBefore(panel, host.firstChild);
    return bodyEl;
  }

  function banner(bodyEl, msg) {
    bodyEl.replaceChildren(el("div", { class: "ta-note" }, msg));
  }

  function pct(sim) {
    return Math.round((sim || 0) * 100);
  }

  async function api(base, path, opts) {
    const r = await fetch(base + path, opts);
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  // ---- Issue page: related pull requests -------------------------------
  async function issuePanel(base, issueId) {
    const body = mountPanel(
      "Related pull requests",
      "PRs already linked to this tracker, plus likely matches."
    );
    banner(body, "Loading…");
    let items;
    try {
      items = await api(base, `/issues/${issueId}/related-prs`);
    } catch (e) {
      return banner(body, "Backend offline — check the TrackerAssist popup.");
    }
    if (!items.length) {
      return banner(
        body,
        "No related pull requests in the scraped data. If the PR is merged, " +
          "it may not be synced yet (closed PRs sync every 6h)."
      );
    }
    body.replaceChildren();
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
      body.append(
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
  function buildMultiFilter(labelText, loadOptions, onChange) {
    const details = el("details", { class: "ta-projfilter" });
    const summary = el("summary", { class: "ta-projsummary" }, labelText);
    const list = el(
      "div",
      { class: "ta-projlist" },
      el("div", { class: "ta-note" }, "Loading…")
    );
    details.append(summary, list);
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
      "Open issues ranked to your profile — already-in-progress work is hidden."
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
    const results = el("div", { class: "ta-results" });
    body.append(note, controls, results);

    function describeMode(m) {
      if (m.mode === "auto")
        note.textContent = `Signed in as ${user} · personalized from your ${m.count} recent Ceph trackers (refine in the popup).`;
      else if (m.mode === "profile")
        note.textContent = `Signed in as ${user} · using your saved profile.`;
      else if (m.mode === "none")
        note.textContent = `Signed in as ${user} · no skills yet — add them in the popup, or nothing was found in your Redmine activity.`;
      else note.textContent = `Signed in as ${user}.`;
    }

    const load = async (force) => {
      banner(results, force ? "Rebuilding from your activity…" : "Ranking issues…");
      const mode = await ensureProfile(force);
      describeMode(mode);
      if (mode.mode === "none") return banner(results, "");
      banner(results, "Ranking issues…");
      // Empty selection -> null, so the backend narrows to your saved areas by
      // default. A non-empty selection scopes the ranking to those values.
      const orNull = (a) => (a.length ? a : null);
      const priorities = orNull(priorityFilter.selected());
      const projects = orNull(projectFilter.selected());
      const trackers = orNull(trackerFilter.selected());
      let recs;
      try {
        recs = await api(base, "/recommendations/issues", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user, priorities, projects, trackers, limit: 12 }),
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
      results.replaceChildren();
      for (const d of recs) {
        const tags = el("div", { class: "ta-tags" });
        for (const t of [d.project_name, d.tracker_name, d.priority]) {
          if (t) tags.append(el("span", { class: "ta-tag" }, t));
        }
        if (d.is_stretch) tags.append(el("span", { class: "ta-tag ta-stretch" }, "stretch pick"));
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
    };

    refresh.addEventListener("click", () => load(false));
    rederive.addEventListener("click", (e) => {
      e.preventDefault();
      load(true);
    });
    load(false);
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
    }
  })();
})();
