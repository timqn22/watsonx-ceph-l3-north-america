// Service worker: seed a sensible default backend URL on install.
// All real work happens in the popup (settings/profile) and content script
// (page panels); this just guarantees a default so first run isn't blank.

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(["backendUrl"], (r) => {
    if (!r.backendUrl) {
      chrome.storage.sync.set({ backendUrl: "http://localhost:8000" });
    }
  });
});
