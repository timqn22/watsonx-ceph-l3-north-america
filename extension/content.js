// Simplified TrackerAssist content script for main branch
// Shows related PRs on Redmine issue pages using existing pr_issue_links.json data

(function () {
  "use strict";

  function storageGet(keys) {
    return new Promise((res) => chrome.storage.sync.get(keys, res));
  }

  // Tiny DOM builder
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
      "PRs linked to this tracker based on semantic similarity."
    );
    banner(body, "Loading…");
    let items;
    try {
      items = await api(base, `/issues/${issueId}/related-prs`);
    } catch (e) {
      return banner(body, "Backend offline — check the TrackerAssist popup or start api_server.py");
    }
    
    // Filter: only show PRs with similarity >= 0.55, max 3 results
    if (items && items.length > 0) {
      items = items
        .filter(pr => (pr.similarity_score || 0) >= 0.55)
        .slice(0, 3);
    }
    
    if (!items || !items.length) {
      return banner(
        body,
        "No related pull requests found in the current data."
      );
    }
    body.replaceChildren();
    for (const s of items) {
      const conf = pct(s.similarity_score);
      const left = el(
        "div",
        { class: "ta-sim" },
        el("div", { class: "ta-bar" }, el("span", { style: `width:${conf}%` })),
        el("div", { class: "ta-simn" }, `${conf}% similarity`)
      );
      const tags = el(
        "div",
        { class: "ta-tags" },
        el("span", { class: "ta-tag" }, s.state || "unknown")
      );
      if (s.labels) {
        for (const label of s.labels.split(',').slice(0, 3)) {
          tags.append(el("span", { class: "ta-tag" }, label.trim()));
        }
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
              { href: s.url || "#", target: "_blank", class: "ta-link" },
              `${s.repo || "ceph/ceph"} #${s.pr_number}`
            ),
            el("div", { class: "ta-desc" }, s.title || ""),
            tags
          )
        )
      );
    }
  }

  // ---- Search panel for issue list pages ------------------------------
  async function searchPanel(base) {
    const body = mountPanel(
      "Search similar issues",
      "Find related Redmine issues using semantic search"
    );

    const searchInput = el("input", {
      type: "text",
      class: "ta-search-input",
      placeholder: "Enter search query (e.g., 'OSD crash', 'RGW performance')...",
    });

    const searchBtn = el("button", { class: "ta-search-btn" }, "Search");
    const resultsDiv = el("div", { class: "ta-search-results" });

    const searchForm = el(
      "div",
      { class: "ta-search-form" },
      searchInput,
      searchBtn
    );

    body.append(searchForm, resultsDiv);

    async function performSearch() {
      const query = searchInput.value.trim();
      if (!query) {
        resultsDiv.replaceChildren(
          el("div", { class: "ta-note" }, "Enter a search query")
        );
        return;
      }

      resultsDiv.replaceChildren(
        el("div", { class: "ta-note" }, "Searching...")
      );

      try {
        const results = await api(
          base,
          `/search?q=${encodeURIComponent(query)}&format=json`
        );

        if (!results || results.length === 0) {
          resultsDiv.replaceChildren(
            el("div", { class: "ta-note" }, "No similar issues found")
          );
          return;
        }

        // Filter: only show issues with similarity >= 0.55
        const filtered = results.filter(r => (r.similarity_score || 0) >= 0.55);
        
        if (filtered.length === 0) {
          resultsDiv.replaceChildren(
            el("div", { class: "ta-note" }, "No similar issues found with similarity >= 55%")
          );
          return;
        }
        
        resultsDiv.replaceChildren();
        for (const r of filtered.slice(0, 10)) {
          // Show top 10 results
          const score = Math.round((r.similarity_score || 0) * 100);
          const metadata = r.metadata || {};

          const tags = el("div", { class: "ta-tags" });
          if (metadata.status) {
            tags.append(el("span", { class: "ta-tag" }, metadata.status));
          }
          if (metadata.priority) {
            tags.append(el("span", { class: "ta-tag" }, metadata.priority));
          }

          resultsDiv.append(
            el(
              "div",
              { class: "ta-card" },
              el(
                "div",
                { class: "ta-sim" },
                el(
                  "div",
                  { class: "ta-bar" },
                  el("span", { style: `width:${score}%` })
                ),
                el("div", { class: "ta-simn" }, `${score}% match`)
              ),
              el(
                "div",
                { class: "ta-info" },
                el(
                  "a",
                  {
                    href: `https://tracker.ceph.com/issues/${r.issue_id}`,
                    target: "_blank",
                    class: "ta-link",
                  },
                  `Issue #${r.issue_id}`
                ),
                el(
                  "div",
                  { class: "ta-desc" },
                  metadata.subject || "No subject"
                ),
                tags
              )
            )
          );
        }
      } catch (e) {
        resultsDiv.replaceChildren(
          el(
            "div",
            { class: "ta-note" },
            "Backend offline — check the TrackerAssist popup or start api_server.py"
          )
        );
      }
    }

    searchBtn.addEventListener("click", performSearch);
    searchInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") performSearch();
    });
  }

  // ---- Route ----------------------------------------------------------
  (async function main() {
    const cfg = await storageGet(["backendUrl"]);
    const base = (cfg.backendUrl || "http://localhost:8000").replace(/\/+$/, "");
    const path = location.pathname;

    const issue = path.match(/\/issues\/(\d+)/);
    if (issue) {
      issuePanel(base, parseInt(issue[1], 10));
    } else if (
      /\/issues\/?$/.test(path) ||
      /\/my\/page/.test(path) ||
      /\/projects\/[^/]+\/issues/.test(path)
    ) {
      searchPanel(base);
    }
  })();
})();

// Made with Bob
