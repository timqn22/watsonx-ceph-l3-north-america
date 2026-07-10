# Ceph Tracker Linker - Browser Extension

AI-powered browser extension that provides intelligent recommendations for linking Ceph trackers and GitHub pull requests.

## Features

- 🔗 **Bidirectional Linking**: Works on both Ceph tracker pages and GitHub PR pages
- 🤖 **AI-Powered**: Uses Sentence Transformers for semantic similarity matching
- 🎯 **Smart Recommendations**: Shows similarity scores and ranked suggestions
- 🌐 **Cross-Browser**: Compatible with Chrome, Edge, and Firefox
- 📊 **Real-time**: Fetches recommendations as you browse

## Architecture

```
Browser Extension (JavaScript)
    ↓ HTTP REST API
Python Service (localhost:5001)
    ↓
- Scrapes Ceph trackers
- Scrapes GitHub PRs
- Generates embeddings
- Calculates similarities
- Returns recommendations
```

## Installation

### Prerequisites

1. **Python API must be running**:
   ```bash
   cd python_service
   source venv/bin/activate
   PORT=5001 python api/app.py
   ```

2. **Browser**: Chrome, Edge, or Firefox

### Chrome/Edge Installation

1. Open Chrome/Edge and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked"
4. Select the `browser_extension` directory
5. The extension icon should appear in your toolbar

### Firefox Installation

1. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Navigate to `browser_extension` directory
4. Select `manifest.json`
5. The extension will be loaded temporarily

## Usage

### On Ceph Tracker Pages

1. Visit any Ceph tracker page: `https://tracker.ceph.com/issues/12345`
2. The extension automatically:
   - Detects the tracker
   - Fetches matching PRs from the API
   - Displays recommendations in a sidebar on the right
3. Click on any recommendation to view the PR
4. Use the similarity score to judge relevance

### On GitHub PR Pages

1. Visit any Ceph PR page: `https://github.com/ceph/ceph/pull/12345`
2. The extension automatically:
   - Detects the PR
   - Fetches matching trackers from the API
   - Displays recommendations in a sidebar on the right
3. Click on any recommendation to view the tracker
4. Use the similarity score to judge relevance

### Extension Popup

Click the extension icon to:
- Check API status
- View current page information
- Refresh recommendations
- Access settings (coming soon)

## File Structure

```
browser_extension/
├── manifest.json           # Extension configuration
├── background.js           # Service worker (API communication)
├── content-tracker.js      # Content script for tracker pages
├── content-github.js       # Content script for GitHub pages
├── sidebar.css            # Sidebar styling
├── popup.html             # Extension popup UI
├── popup.js               # Popup logic
├── icons/                 # Extension icons
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md              # This file
```

## How It Works

### 1. Page Detection
- Content scripts detect when you're on a tracker or PR page
- Extract relevant information (ID, title, description, etc.)

### 2. API Communication
- Background service worker handles all API calls
- Sends tracker/PR info to Python API
- Receives recommendations with similarity scores

### 3. UI Injection
- Sidebar is injected into the page
- Displays current item info
- Shows ranked recommendations
- Provides quick actions (view, copy link)

### 4. Similarity Scoring
- **High (70%+)**: Green badge - Strong match
- **Medium (50-69%)**: Yellow badge - Moderate match
- **Low (<50%)**: Gray badge - Weak match

## Troubleshooting

### Extension Not Working

1. **Check API Status**:
   - Click extension icon
   - Should show "API is running"
   - If not, start Python API: `cd python_service && python api/app.py`

2. **Check Console**:
   - Right-click page → Inspect → Console
   - Look for "Ceph Tracker Linker" messages
   - Check for errors

3. **Reload Extension**:
   - Go to `chrome://extensions/`
   - Click reload icon on the extension
   - Refresh the page you're viewing

### No Recommendations Shown

1. **API might be processing**:
   - First load can take 30-60 seconds
   - API needs to download embeddings model
   - Check Python API logs

2. **No matches found**:
   - Tracker/PR might be too unique
   - Try adjusting similarity threshold in API config

3. **Already linked**:
   - Extension only shows unlinked items
   - Check if tracker/PR already has links

### Sidebar Not Appearing

1. **Check page URL**:
   - Must be `tracker.ceph.com/issues/*` or `github.com/ceph/ceph/pull/*`
   - Extension only works on these domains

2. **Content script blocked**:
   - Some pages might block content scripts
   - Check browser console for errors

## Configuration

### API Endpoint

Default: `http://localhost:5001`

To change:
1. Edit `background.js`
2. Update `API_BASE_URL` constant
3. Reload extension

### Similarity Threshold

Controlled by Python API, not extension.

Edit `python_service/config.py`:
```python
MIN_SIMILARITY_SCORE = 0.5  # Adjust as needed
```

## Development

### Testing Locally

1. Make changes to extension files
2. Go to `chrome://extensions/`
3. Click reload icon
4. Refresh the page you're testing on

### Debugging

**Background Script**:
- Go to `chrome://extensions/`
- Click "Inspect views: service worker"
- View console logs

**Content Scripts**:
- Right-click page → Inspect
- Console tab shows content script logs

**API Calls**:
- Network tab shows API requests
- Check response status and data

## Browser Compatibility

### Chrome/Edge (Manifest V3)
- ✅ Fully supported
- Uses service worker for background tasks
- Modern API calls

### Firefox (Manifest V2/V3)
- ✅ Supported with compatibility layer
- `browser_specific_settings` in manifest
- May need minor adjustments for older versions

## Security & Privacy

- **Local Only**: All data stays on your machine
- **No Tracking**: Extension doesn't collect any data
- **API Keys**: No external API keys required
- **Open Source**: All code is visible and auditable

## Future Enhancements

- [ ] Settings page for configuration
- [ ] Manual link creation from extension
- [ ] Batch processing of multiple trackers/PRs
- [ ] Export recommendations to CSV
- [ ] Dark mode toggle
- [ ] Keyboard shortcuts
- [ ] Notification system

## Support

For issues or questions:
1. Check Python API logs
2. Check browser console
3. Review this README
4. Check main project documentation

## License

Same as parent project.