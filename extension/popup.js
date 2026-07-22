// Popup: manage connection settings + the signed-in user's skill profile.
// Settings live in chrome.storage.sync; the profile is persisted to the backend
// keyed by the user's ID, so recommendations personalize per person.

const $ = (id) => document.getElementById(id);
const CSV = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

function setStatus(msg, ok) {
  const el = $("status");
  el.textContent = msg;
  el.className = "status " + (ok ? "ok" : "err");
}

function normalizeBackend(url) {
  return (url || "http://localhost:8000").replace(/\/+$/, "");
}

// Load saved settings, then hydrate the profile fields from the backend.
chrome.storage.sync.get(["backendUrl", "userId"], async (cfg) => {
  $("backendUrl").value = cfg.backendUrl || "http://localhost:8000";
  $("userId").value = cfg.userId || "";
  if (!cfg.userId) return;
  try {
    const base = normalizeBackend(cfg.backendUrl);
    const r = await fetch(`${base}/profiles/${encodeURIComponent(cfg.userId)}`);
    if (!r.ok) return;
    const p = await r.json();
    $("displayName").value = p.display_name || "";
    $("skills").value = p.skill_prompt || "";
    $("background").value = p.background || "";
    $("projects").value = (p.preferred_projects || []).join(", ");
    $("trackers").value = (p.preferred_trackers || []).join(", ");
  } catch (e) {
    // Backend offline is fine; user can still edit and save later.
  }
});

$("save").addEventListener("click", async () => {
  const backendUrl = normalizeBackend($("backendUrl").value);
  const userId = $("userId").value.trim();
  chrome.storage.sync.set({ backendUrl, userId });

  if (!userId) {
    setStatus("Saved connection. Add an ID to save a profile.", true);
    return;
  }
  const body = {
    skill_prompt: $("skills").value,
    background: $("background").value,
    display_name: $("displayName").value || null,
    preferred_projects: CSV($("projects").value),
    preferred_trackers: CSV($("trackers").value),
    preferred_priorities: null,
  };
  try {
    const r = await fetch(`${backendUrl}/profiles/${encodeURIComponent(userId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    setStatus("Profile saved. Open a Redmine issues page to see picks.", true);
  } catch (e) {
    setStatus("Could not reach backend at " + backendUrl, false);
  }
});

// Duplicate detection functionality
function setDuplicateStatus(msg, ok) {
  const el = $("duplicateStatus");
  el.textContent = msg;
  el.className = "status " + (ok ? "ok" : "err");
}

function renderDuplicateGroups(groups) {
  const container = $("duplicateResults");
  if (!groups || groups.length === 0) {
    container.innerHTML = '<div style="color: #9aa2b1; font-size: 12px;">No duplicate groups found.</div>';
    return;
  }

  let html = '';
  groups.forEach((group, idx) => {
    const confidence = Math.round(group.max_confidence * 100);
    html += `
      <div style="background: #1a1d24; border: 1px solid #333a47; border-radius: 6px; padding: 10px; margin-bottom: 10px;">
        <div style="color: #7cc5ff; font-weight: bold; margin-bottom: 6px;">
          Group ${idx + 1} (${group.group_size} trackers, ${confidence}% confidence)
        </div>
    `;
    
    group.trackers.forEach((tracker, tIdx) => {
      const trackerConfidence = Math.round(tracker.confidence * 100);
      const statusColor = tracker.is_open ? '#5fd18b' : '#9aa2b1';
      html += `
        <div style="margin-left: 10px; margin-bottom: 6px; padding: 6px; background: #0f1115; border-radius: 4px;">
          <div style="font-size: 12px;">
            <a href="${tracker.url}" target="_blank" style="color: #e7e9ee; text-decoration: none;">
              #${tracker.issue_id}: ${tracker.subject || 'No subject'}
            </a>
          </div>
          <div style="font-size: 11px; color: #9aa2b1; margin-top: 2px;">
            ${tracker.project_name || 'Unknown'} • ${tracker.tracker_name || 'Unknown'} •
            <span style="color: ${statusColor}">${tracker.status || 'Unknown'}</span>
            ${tIdx > 0 ? ` • ${trackerConfidence}% similar` : ''}
            ${tracker.assignee ? ` • Assigned to ${tracker.assignee}` : ''}
          </div>
        </div>
      `;
    });
    
    html += '</div>';
  });
  
  container.innerHTML = html;
}

$("detectDuplicates").addEventListener("click", async () => {
  const backendUrl = normalizeBackend($("backendUrl").value);
  setDuplicateStatus("Detecting duplicates...", true);
  $("duplicateResults").innerHTML = '';
  
  try {
    const r = await fetch(`${backendUrl}/duplicates/detect?min_similarity=0.92&limit=20`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    
    const groups = await r.json();
    setDuplicateStatus(`Found ${groups.length} duplicate group(s)`, true);
    renderDuplicateGroups(groups);
  } catch (e) {
    setDuplicateStatus("Could not reach backend at " + backendUrl, false);
    $("duplicateResults").innerHTML = '';
  }
});
