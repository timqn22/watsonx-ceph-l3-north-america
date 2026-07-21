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
