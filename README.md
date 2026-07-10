# Ceph Tracker Linker

AI-powered browser extension that intelligently links Ceph project trackers with GitHub pull requests using semantic similarity analysis.

## 🎯 Overview

This project provides a **browser extension** that automatically suggests relevant linkages between:
- **Ceph Trackers** (Redmine issues at tracker.ceph.com)
- **GitHub Pull Requests** (ceph/ceph repository)

The extension uses **AI embeddings** (Sentence Transformers) to understand the semantic meaning of trackers and PRs, then recommends the most relevant matches based on similarity scores.

## ✨ Key Features

- 🔗 **Bidirectional Recommendations**: Works on both tracker pages and PR pages
- 🤖 **AI-Powered Matching**: Uses Sentence Transformers for semantic understanding
- 🎯 **Smart Scoring**: Color-coded similarity scores (70%+ = high, 50-69% = medium, <50% = low)
- 🌐 **Cross-Browser**: Compatible with Chrome, Edge, and Firefox
- 📊 **Real-Time**: Fetches recommendations as you browse
- 🔒 **Privacy-First**: All processing happens locally, no external API keys needed
- ⚡ **Fast**: Cached embeddings for quick subsequent loads

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│   Browser Extension (JavaScript)        │
│   - Detects tracker/PR pages            │
│   - Injects sidebar UI                  │
│   - Displays recommendations            │
└──────────────┬──────────────────────────┘
               │ HTTP REST API
               ▼
┌─────────────────────────────────────────┐
│   Python Service (localhost:5001)       │
│   ┌─────────────────────────────────┐   │
│   │ Scrapers                        │   │
│   │ - Ceph tracker scraper          │   │
│   │ - GitHub PR scraper             │   │
│   └─────────────────────────────────┘   │
│   ┌─────────────────────────────────┐   │
│   │ AI Engine                       │   │
│   │ - Sentence Transformers         │   │
│   │ - Embedding generation          │   │
│   │ - Similarity calculation        │   │
│   └─────────────────────────────────┘   │
│   ┌─────────────────────────────────┐   │
│   │ Flask REST API (9 endpoints)    │   │
│   │ - Health check                  │   │
│   │ - Get recommendations           │   │
│   │ - Scrape trackers/PRs           │   │
│   └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** with pip
- **Node.js** (optional, for development)
- **Chrome, Edge, or Firefox** browser
- **Git** (to clone the repository)

### Installation

#### 1. Clone Repository

```bash
git clone <repository-url>
cd watsonx-ceph-l3-north-america
```

#### 2. Set Up Python Service

```bash
# Navigate to Python service
cd python_service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env if needed (optional GitHub token for higher rate limits)
nano .env
```

#### 3. Start Python API

```bash
# Make sure you're in python_service/ with venv activated
PORT=5001 python api/app.py
```

**First run**: Downloads Sentence Transformers model (~90MB), takes 30-60 seconds.

Keep this terminal running!

#### 4. Install Browser Extension

**Chrome/Edge**:
1. Open `chrome://extensions/`
2. Enable "Developer mode" (top-right toggle)
3. Click "Load unpacked"
4. Select `browser_extension/` directory
5. Extension icon appears in toolbar

**Firefox**:
1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `browser_extension/manifest.json`
4. Extension loads (temporary)

### 5. Test It!

Visit any Ceph tracker or PR:
- **Tracker**: https://tracker.ceph.com/issues/12345
- **PR**: https://github.com/ceph/ceph/pull/12345

You should see a sidebar with recommendations!

## 📖 Documentation

- **[Browser Extension Guide](BROWSER_EXTENSION_GUIDE.md)** - Installation, usage, troubleshooting
- **[Architecture Details](ARCHITECTURE.md)** - System design and components
- **[API Documentation](python_service/API_DOCUMENTATION.md)** - REST API reference
- **[Quick Start Guide](python_service/QUICK_START.md)** - Python service setup

## 🎨 How It Works

### 1. Page Detection
When you visit a Ceph tracker or GitHub PR page, the extension:
- Detects the page type (tracker or PR)
- Extracts relevant information (ID, title, description, etc.)
- Sends request to Python API

### 2. AI Processing
The Python service:
- Scrapes unlinked trackers and PRs
- Generates embeddings using Sentence Transformers (all-MiniLM-L6-v2)
- Calculates cosine similarity between embeddings
- Ranks matches by similarity score

### 3. Display Results
The extension:
- Injects a sidebar into the page
- Shows top recommendations with similarity scores
- Provides quick actions (view, copy link)
- Color-codes by relevance (green/yellow/gray)

## 🔧 Configuration

### Python Service

Edit `python_service/.env`:

```bash
# Ceph Tracker Configuration
CEPH_TRACKER_URL=https://tracker.ceph.com

# GitHub Configuration
GITHUB_REPO=ceph/ceph
GITHUB_TOKEN=your_token_here  # Optional, for higher rate limits

# API Configuration
PORT=5001
MIN_SIMILARITY_SCORE=0.5  # Adjust threshold (0.0-1.0)
```

### Browser Extension

Default API endpoint: `http://localhost:5001`

To change, edit `browser_extension/background.js`:
```javascript
const API_BASE_URL = 'http://localhost:5001';
```

## 📊 Project Statistics

- **40+ files** across Python service and browser extension
- **4,000+ lines of code**
- **9 REST API endpoints**
- **2 content scripts** (tracker + GitHub)
- **3 scrapers** (trackers, PRs, embeddings)
- **Zero external API keys required** (uses open-source models)

## 🧪 Testing

### Test Python API

```bash
cd python_service
source venv/bin/activate

# Run complete pipeline test
python test_complete.py

# Run API endpoint tests
python test_api.py
```

### Test Browser Extension

1. Start Python API
2. Load extension in browser
3. Visit test pages:
   - Tracker: https://tracker.ceph.com/issues/12345
   - PR: https://github.com/ceph/ceph/pull/12345
4. Check sidebar appears with recommendations

See [BROWSER_EXTENSION_GUIDE.md](BROWSER_EXTENSION_GUIDE.md) for detailed testing checklist.

## 🐛 Troubleshooting

### Extension Not Working

**Check API Status**:
```bash
# Should show: "Running on http://127.0.0.1:5001"
cd python_service
source venv/bin/activate
PORT=5001 python api/app.py
```

**Check Extension**:
1. Click extension icon
2. Should show "API is running" (green)
3. If red, API is not running

### No Recommendations

**Possible causes**:
- First load (model downloading, wait 60s)
- No semantic matches found
- Tracker/PR already linked
- API processing (check Python logs)

### Sidebar Not Appearing

**Check URL**:
- Must be `tracker.ceph.com/issues/*` or `github.com/ceph/ceph/pull/*`
- Extension only works on these domains

**Check Console**:
- Right-click page → Inspect → Console
- Look for "Ceph Tracker Linker" messages
- Check for errors

## 🔒 Security & Privacy

- ✅ **Local Processing**: All AI processing happens on your machine
- ✅ **No Tracking**: Extension doesn't collect or send any data
- ✅ **No External APIs**: Uses open-source models (Sentence Transformers)
- ✅ **Optional GitHub Token**: Only for higher rate limits, not required
- ✅ **Open Source**: All code is visible and auditable

## 🛠️ Technology Stack

### Python Service
- **Flask** - REST API framework
- **Sentence Transformers** - AI embeddings (all-MiniLM-L6-v2)
- **Requests** - HTTP client for scraping
- **BeautifulSoup4** - HTML parsing
- **NumPy** - Numerical computations
- **Python-dotenv** - Environment configuration

### Browser Extension
- **Vanilla JavaScript** - No frameworks, lightweight
- **Manifest V3** - Modern extension API
- **Chrome/Firefox APIs** - Cross-browser compatibility
- **CSS3** - Modern styling with dark mode support

## 📈 Performance

### First Load
- Model download: 30-60 seconds (one-time)
- Embedding generation: 5-10 seconds
- Similarity calculation: 1-2 seconds

### Subsequent Loads
- Cached embeddings: 1-2 seconds
- Much faster after first use

### Memory Usage
- Python API: ~500 MB (model in memory)
- Browser extension: ~10-20 MB

## 🚧 Future Enhancements

- [ ] Settings page for configuration
- [ ] Manual link creation from extension
- [ ] Batch processing of multiple items
- [ ] Export recommendations to CSV
- [ ] Keyboard shortcuts
- [ ] Notification system
- [ ] Support for other Ceph projects
- [ ] Integration with Redmine API for automatic linking

## 📝 Development

### Project Structure

```
watsonx-ceph-l3-north-america/
├── python_service/              # Backend API
│   ├── api/                     # Flask REST API
│   ├── scrapers/                # Data collection
│   ├── embeddings/              # AI embeddings
│   ├── similarity/              # Similarity calculation
│   ├── config.py                # Configuration
│   ├── requirements.txt         # Python dependencies
│   └── tests/                   # Test files
├── browser_extension/           # Frontend extension
│   ├── manifest.json            # Extension config
│   ├── background.js            # Service worker
│   ├── content-tracker.js       # Tracker page script
│   ├── content-github.js        # GitHub page script
│   ├── sidebar.css              # Styling
│   ├── popup.html/js            # Extension popup
│   └── icons/                   # Extension icons
├── ARCHITECTURE.md              # System architecture
├── BROWSER_EXTENSION_GUIDE.md   # Extension guide
└── README.md                    # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- **Ceph Project** - For the amazing distributed storage system
- **Sentence Transformers** - For open-source embedding models
- **Hugging Face** - For model hosting and tools

## 📞 Support

For issues or questions:
1. Check documentation files
2. Review troubleshooting sections
3. Check browser console for errors
4. Check Python API logs
5. Open an issue on GitHub

## 🎉 Success!

If you see recommendations in the sidebar, congratulations! The system is working. The AI is now helping you discover relevant linkages between Ceph trackers and pull requests.

Happy linking! 🔗
