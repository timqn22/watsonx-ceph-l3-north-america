# Browser Extension Installation & Testing Guide

Complete guide for installing and testing the Ceph Tracker Linker browser extension.

## Quick Start

### 1. Start Python API (Required!)

```bash
cd python_service
source venv/bin/activate
PORT=5001 python api/app.py
```

Keep this running in a terminal. The extension won't work without it.

### 2. Install Extension

#### Chrome/Edge

1. Open browser and go to: `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **"Load unpacked"**
4. Navigate to and select: `browser_extension/` directory
5. Extension should appear with a blue "C" icon

#### Firefox

1. Open Firefox and go to: `about:debugging#/runtime/this-firefox`
2. Click **"Load Temporary Add-on..."**
3. Navigate to `browser_extension/` directory
4. Select `manifest.json` file
5. Extension loads (temporary - removed when Firefox closes)

### 3. Test It!

Visit one of these pages:
- **Tracker**: https://tracker.ceph.com/issues/12345 (any valid tracker)
- **PR**: https://github.com/ceph/ceph/pull/12345 (any valid PR)

You should see:
- Sidebar appears on the right side
- "Checking API connection..." message
- Then recommendations load (or "No matches found")

## What You'll See

### On Tracker Pages

```
┌─────────────────────────────────────┐
│  🔗 PR Recommendations              │
├─────────────────────────────────────┤
│  Current Tracker                    │
│  #12345: Fix memory leak in OSD     │
│  Status: New | Priority: High       │
├─────────────────────────────────────┤
│  Recommended PRs (3)                │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ PR #54321: Memory fixes  85%│   │
│  │ State: open | Author: dev1  │   │
│  │ [View PR] [Copy Link]       │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ PR #54320: OSD cleanup   72%│   │
│  │ ...                         │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### On GitHub PR Pages

Same layout, but shows matching **trackers** instead of PRs.

## Testing Checklist

### ✅ Basic Functionality

- [ ] Extension icon appears in toolbar
- [ ] Click icon → popup shows API status
- [ ] Visit tracker page → sidebar appears
- [ ] Visit PR page → sidebar appears
- [ ] Recommendations load (or "No matches" message)
- [ ] Click recommendation → opens in new tab
- [ ] Toggle button (✕) collapses sidebar

### ✅ API Integration

- [ ] Popup shows "API is running" (green)
- [ ] If API stopped → shows error message
- [ ] Recommendations have similarity scores
- [ ] Scores are color-coded (green/yellow/gray)

### ✅ UI/UX

- [ ] Sidebar doesn't block page content
- [ ] Sidebar is scrollable if many recommendations
- [ ] Hover effects work on recommendations
- [ ] Links open in new tabs
- [ ] Copy button works (copies URL to clipboard)

### ✅ Error Handling

- [ ] API not running → clear error message
- [ ] Invalid page → no sidebar appears
- [ ] No matches → friendly "No matches found" message
- [ ] Network error → error displayed in sidebar

## Troubleshooting

### Problem: Extension Icon Not Showing

**Solution**:
1. Go to `chrome://extensions/` (or Firefox equivalent)
2. Check if extension is enabled
3. Look for errors in the extension card
4. Try reloading the extension

### Problem: Sidebar Not Appearing

**Possible Causes**:

1. **Wrong URL**:
   - Must be `tracker.ceph.com/issues/*` or `github.com/ceph/ceph/pull/*`
   - Extension only works on these specific domains

2. **Content Script Error**:
   - Right-click page → Inspect → Console
   - Look for red errors
   - Check if "Ceph Tracker Linker" messages appear

3. **Extension Not Loaded**:
   - Refresh the extension in `chrome://extensions/`
   - Reload the page

### Problem: "API Not Running" Error

**Solution**:
```bash
# Terminal 1: Start API
cd python_service
source venv/bin/activate
PORT=5001 python api/app.py

# Wait for: "Running on http://127.0.0.1:5001"
```

Then:
1. Click extension icon
2. Should show "API is running" (green)
3. Refresh the tracker/PR page

### Problem: No Recommendations Shown

**Possible Causes**:

1. **First Load (Model Download)**:
   - First time takes 30-60 seconds
   - API downloads Sentence Transformers model
   - Check Python API terminal for progress
   - Wait and refresh page

2. **No Matches**:
   - Tracker/PR might be too unique
   - Try a different tracker/PR
   - Check similarity threshold in `python_service/config.py`

3. **Already Linked**:
   - Extension only shows unlinked items
   - If tracker already has PR links, won't show recommendations

### Problem: Sidebar Blocks Content

**Solution**:
- Click the ✕ button to collapse sidebar
- Sidebar slides off-screen but stays accessible
- Click ☰ to expand again

## Advanced Testing

### Test Different Scenarios

1. **High Similarity Match**:
   - Find tracker with clear PR match
   - Should show 70%+ similarity (green badge)

2. **No Matches**:
   - Find very specific/unique tracker
   - Should show "No matching PRs found"

3. **Multiple Matches**:
   - Find popular tracker
   - Should show multiple recommendations ranked by score

4. **API Offline**:
   - Stop Python API
   - Refresh page
   - Should show clear error message with instructions

### Test Both Directions

1. **Tracker → PR**:
   - Visit tracker page
   - See PR recommendations

2. **PR → Tracker**:
   - Visit GitHub PR page
   - See tracker recommendations

### Test Browser Compatibility

1. **Chrome/Edge**:
   - Should work identically
   - Uses Manifest V3

2. **Firefox**:
   - Should work with minor differences
   - Uses compatibility layer

## Performance Notes

### First Load
- **30-60 seconds**: Model download (one-time)
- **5-10 seconds**: Generate embeddings
- **1-2 seconds**: Calculate similarities

### Subsequent Loads
- **1-2 seconds**: Cached embeddings
- Much faster after first use

### Memory Usage
- **Extension**: ~10-20 MB
- **Python API**: ~500 MB (model in memory)

## Development Tips

### Viewing Logs

**Background Script Logs**:
```
1. Go to chrome://extensions/
2. Find "Ceph Tracker Linker"
3. Click "Inspect views: service worker"
4. Console shows background.js logs
```

**Content Script Logs**:
```
1. Right-click on tracker/PR page
2. Click "Inspect"
3. Console tab
4. Look for "Ceph Tracker Linker" messages
```

**Python API Logs**:
```
Check terminal where you ran:
python api/app.py

Shows all API requests and responses
```

### Making Changes

1. Edit extension files
2. Go to `chrome://extensions/`
3. Click reload icon on extension
4. Refresh the page you're testing

No need to reinstall!

### Testing API Calls

Use browser DevTools:
1. Right-click page → Inspect
2. Network tab
3. Filter: "localhost:5001"
4. See all API requests/responses

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| No sidebar | Wrong URL | Visit tracker.ceph.com or github.com/ceph/ceph |
| API error | Python not running | Start: `python api/app.py` |
| Slow first load | Model download | Wait 60s, then refresh |
| No recommendations | No matches found | Try different tracker/PR |
| Extension missing | Not loaded | Load unpacked in chrome://extensions |

## Next Steps

After successful testing:

1. **Use It**: Browse trackers and PRs normally
2. **Provide Feedback**: Note any issues or improvements
3. **Share**: Help others install and use it

## Support

If you encounter issues:

1. Check this guide
2. Check browser console for errors
3. Check Python API logs
4. Review `browser_extension/README.md`
5. Check main project documentation

## Files Reference

```
browser_extension/
├── manifest.json          # Extension config
├── background.js          # API communication
├── content-tracker.js     # Tracker page logic
├── content-github.js      # GitHub page logic
├── sidebar.css           # Styling
├── popup.html/js         # Extension popup
└── icons/                # Extension icons
```

All files are in the `browser_extension/` directory.