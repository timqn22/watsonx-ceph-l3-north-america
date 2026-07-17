# Browser Extension Setup Guide

## Overview

The Ceph Redmine Browser Extension displays related GitHub PRs directly on Redmine tracker pages. When you visit any issue on tracker.ceph.com, the extension automatically shows a panel with related pull requests based on semantic similarity.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser Extension                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Content Script (runs on tracker.ceph.com)             │ │
│  │  - Detects issue pages                                 │ │
│  │  - Extracts issue ID from URL                          │ │
│  │  - Injects "Related PRs" panel                         │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                           │
└───────────────────┼───────────────────────────────────────────┘
                    │ HTTP Request
                    │ GET /issues/{id}/related-prs
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              API Server (localhost:8000)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  /issues/{issue_id}/related-prs endpoint               │ │
│  │  - Reads issue_pr_links.json                           │ │
│  │  - Returns PR data with similarity scores              │ │
│  │  - Enables CORS for extension access                   │ │
│  └────────────────┬───────────────────────────────────────┘ │
└───────────────────┼───────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Data Files (JSON)                               │
│  - issue_pr_links.json: Issue → PR mappings                 │
│  - pr_issue_links.json: PR → Issue mappings                 │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **API Server Running**: The extension requires the API server to be running
2. **Data Generated**: You need `issue_pr_links.json` file with PR mappings
3. **Chrome or Edge Browser**: Extension uses Manifest V3

## Installation Steps

### 1. Generate PR-Issue Mappings

First, ensure you have the necessary data files:

```bash
# Generate issue → PR mappings (required for extension)
python3 generate_issue_pr_links.py

# This creates issue_pr_links.json with structure:
# [
#   {
#     "issue": {...},
#     "similar_prs": [
#       {
#         "pr_number": 12345,
#         "similarity_score": 0.85,
#         "metadata": {...},
#         "document": "PR description..."
#       }
#     ]
#   }
# ]
```

### 2. Start the API Server

The extension communicates with the local API server:

```bash
python3 api_server.py
```

The server will start on `http://localhost:8000` and provide the `/issues/{issue_id}/related-prs` endpoint.

### 3. Load the Extension

#### Chrome:
1. Open `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked"
4. Navigate to and select the `extension/` directory
5. The extension icon should appear in your toolbar

#### Edge:
1. Open `edge://extensions/`
2. Enable "Developer mode" (toggle in left sidebar)
3. Click "Load unpacked"
4. Navigate to and select the `extension/` directory
5. The extension icon should appear in your toolbar

### 4. Configure Backend URL (Optional)

By default, the extension connects to `http://localhost:8000`. To change this:

1. Click the extension icon in your toolbar
2. Enter a different backend URL if needed
3. Click "Save Settings"

## Usage

1. **Visit a Ceph Issue**: Navigate to any issue on tracker.ceph.com
   - Example: https://tracker.ceph.com/issues/12345

2. **View Related PRs**: The extension automatically injects a panel showing:
   - Related GitHub PRs with similarity scores
   - PR status (open/closed/merged)
   - PR labels and authors
   - Direct links to PRs on GitHub

3. **Click to View**: Click any PR link to open it on GitHub

## Extension Features

### What It Shows

- **PR Number & Title**: Direct link to the PR on GitHub
- **Similarity Score**: How closely the PR matches the issue (0.0 - 1.0)
- **Status**: Open, Closed, or Merged
- **Labels**: PR labels (e.g., "bug", "enhancement")
- **Author**: GitHub username of PR creator

### What It Doesn't Do

- ❌ No user profiles or authentication
- ❌ No personalized recommendations
- ❌ No database storage (reads from JSON files)
- ❌ No complex backend features

This is a simplified version focused solely on displaying related PRs.

## Troubleshooting

### Extension Not Showing PRs

1. **Check API Server**: Ensure `api_server.py` is running on port 8000
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check Data File**: Verify `issue_pr_links.json` exists and contains data
   ```bash
   ls -lh issue_pr_links.json
   ```

3. **Check Browser Console**: 
   - Open DevTools (F12)
   - Look for errors in the Console tab
   - Check Network tab for failed API requests

4. **Verify Issue ID**: The extension extracts the issue ID from the URL
   - URL format: `https://tracker.ceph.com/issues/12345`
   - Issue ID: `12345`

### CORS Errors

If you see CORS errors in the browser console:

1. Verify the API server has CORS enabled (it should by default)
2. Check that you're accessing the API from `tracker.ceph.com` (not localhost)
3. Restart the API server

### No Data for Issue

If the panel shows "No related PRs found":

1. The issue may not have any similar PRs in the database
2. Run `generate_issue_pr_links.py` to update mappings
3. Ensure the PR vector database is populated:
   ```bash
   python3 backport_prs.py  # Fetch historical PRs
   ```

## Data Flow

1. **User visits issue page** → Extension detects URL pattern
2. **Extract issue ID** → Parse from URL (e.g., `/issues/12345`)
3. **API request** → `GET http://localhost:8000/issues/12345/related-prs`
4. **Server reads JSON** → Load `issue_pr_links.json`
5. **Find matching issue** → Search for issue ID in JSON
6. **Return PR data** → Format and send to extension
7. **Display panel** → Inject HTML with PR information

## File Structure

```
extension/
├── manifest.json          # Extension configuration (Manifest V3)
├── content.js            # Injects PR panel on Redmine pages
├── content.css           # Styling for injected panel
├── popup.html            # Settings popup UI
├── popup.js              # Settings popup logic
├── background.js         # Service worker (minimal)
├── icon16.png            # Extension icon (16x16)
├── icon48.png            # Extension icon (48x48)
├── icon128.png           # Extension icon (128x128)
└── README.md             # Extension-specific documentation
```

## API Endpoint Details

### GET /issues/{issue_id}/related-prs

Returns related PRs for a specific issue.

**Request:**
```
GET http://localhost:8000/issues/12345/related-prs
```

**Response:**
```json
{
  "issue_id": "12345",
  "related_prs": [
    {
      "pr_number": 54321,
      "title": "Fix OSD crash on startup",
      "url": "https://github.com/ceph/ceph/pull/54321",
      "state": "merged",
      "labels": "bug,backport-needed",
      "author": "username",
      "similarity_score": 0.85,
      "repo": "ceph/ceph"
    }
  ]
}
```

**Error Response:**
```json
{
  "error": "Issue not found"
}
```

## Updating the Extension

After making changes to extension files:

1. Go to `chrome://extensions/` or `edge://extensions/`
2. Find the "Ceph Redmine Extension"
3. Click the refresh icon (🔄)
4. Reload any open Redmine pages

## Security Notes

- Extension only runs on `tracker.ceph.com` (defined in manifest)
- API calls are made to `localhost:8000` only
- No external API keys or authentication required
- No data is sent to external servers
- All processing happens locally

## Performance

- **Lightweight**: Minimal JavaScript, no heavy libraries
- **Fast**: Direct JSON file reads, no database queries
- **Efficient**: Only activates on Redmine issue pages
- **Non-intrusive**: Doesn't modify existing page content

## Future Enhancements

Possible improvements (not currently implemented):

- [ ] Cache API responses to reduce server load
- [ ] Add filtering options (by PR status, labels, etc.)
- [ ] Show PR descriptions in tooltips
- [ ] Add "Copy PR link" button
- [ ] Display PR creation/merge dates
- [ ] Show PR review status
- [ ] Add dark mode support

## Support

For issues or questions:

1. Check the browser console for errors
2. Verify API server logs
3. Review `issue_pr_links.json` structure
4. See main [README.md](README.md) for system overview