# TrackerAssist browser extension

A Manifest V3 extension that surfaces TrackerAssist directly on Redmine pages —
no separate dashboard tab needed. **No build step**: it's plain JavaScript, so
you just load the folder.

## What it does

- **On an issue page** (`/issues/123`): injects a **Related pull requests**
  panel — PRs that likely belong to this tracker, each with a similarity bar and
  **Accept / Ignore** buttons.
- **On issue listings / My page**: injects a **Recommended for you** panel —
  open issues ranked to *your* profile, with a **priority dropdown** (Low /
  Normal / High / Urgent / Immediate). Work already in progress is hidden.
  **You don't have to fill anything in**: it auto-signs-in with your Redmine
  login and builds your profile from the trackers you've been assigned/authored.
  Use the popup only to refine skills, or click "Rebuild from my activity" to
  refresh it.

Everything talks to your TrackerAssist backend; the extension itself holds no
credentials — just the backend URL and your user id.

## Install (Chrome or Edge)

1. Make sure the backend is running (`uvicorn app.main:app` — see `../backend`).
2. Open `chrome://extensions` (or `edge://extensions`).
3. Turn on **Developer mode** (top-right).
4. Click **Load unpacked** and select this `extension/` folder.
5. Click the TrackerAssist toolbar icon to open the popup:
   - **Backend URL** — e.g. `http://localhost:8000` (default).
   - **Your ID** — any handle (e.g. `eleson`). This "signs you in" and is the
     key your profile is saved under.
   - Fill in **Skills** and **Previous projects**, optionally preferred
     projects/trackers, then **Save profile**.
6. Visit a Redmine issue page or issue list on **tracker.ceph.com** — the panels
   appear at the top of the content area.

## Notes

- Content scripts are scoped to `https://tracker.ceph.com/*`. To use another
  Redmine host, add it to `host_permissions` and `content_scripts.matches` in
  `manifest.json`, then reload the extension.
- The backend enables permissive CORS for the hackathon, and Chrome treats
  `localhost` as a secure origin, so the page can call your local backend.
- Firefox is out of scope (MV3 background-worker differences).
- If a panel shows "Backend offline", check the Backend URL in the popup and that
  the server is running.
