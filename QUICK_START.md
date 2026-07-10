# Quick Start Guide

## Setup (5 minutes)

### 1. Copy and Edit .env File

**DO NOT edit `.env.example`** - it's a template!

```bash
cd python_service

# Copy the template to create your actual .env file
cp .env.example .env

# Now edit .env (not .env.example!)
nano .env   # or use any text editor
```

### 2. What to Put in .env

**Minimal setup** (for testing):
```bash
# GitHub Configuration (OPTIONAL - but recommended)
GITHUB_TOKEN=your_token_here_or_leave_empty
GITHUB_REPO=ceph/ceph

# Ceph Tracker Configuration
CEPH_TRACKER_URL=https://tracker.ceph.com
CEPH_PROJECT_ID=    # Leave empty - it's optional!

# Embedding Model (already set, no changes needed)
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_CACHE_DIR=./models

# Everything else can stay as-is
```

**What you need to change**:
- `GITHUB_TOKEN`: Add your token OR leave empty (will work but slower)
- Everything else: **Leave as-is** for testing

## Scraping Limits (Built-in for Testing!)

**Good news**: The test scripts already limit scraping for you!

### test_scrapers.py
```python
# Only fetches 5 items by default
trackers = scraper.fetch_unlinked_trackers(limit=5)
prs = scraper.fetch_unlinked_prs(limit=5)
```

### test_complete.py
```python
# Only fetches 3 items for testing
trackers = scraper.fetch_unlinked_trackers(limit=3)
prs = scraper.fetch_unlinked_prs(limit=3)
```

### Custom Limits

You can easily change the limits:

```python
# In your own code
from scrapers import CephTrackerScraper, GithubPRScraper

# Fetch only 10 trackers
with CephTrackerScraper() as scraper:
    trackers = scraper.fetch_unlinked_trackers(limit=10)

# Fetch only 20 PRs
with GithubPRScraper() as scraper:
    prs = scraper.fetch_unlinked_prs(limit=20)
```

## Complete Setup Steps

```bash
# 1. Navigate to python service
cd python_service

# 2. Run setup script
./setup.sh

# 3. Activate virtual environment
source venv/bin/activate

# 4. Copy .env template
cp .env.example .env

# 5. Edit .env (optional - add GitHub token)
nano .env

# 6. Test scrapers only (fast, 5 items each)
python test_scrapers.py

# 7. Test complete pipeline (slower, 3 items each)
python test_complete.py
```

## What Each Test Does

### test_scrapers.py (Fast - ~10 seconds)
- Fetches 5 trackers
- Fetches 5 PRs
- Shows results
- **No embeddings** (fast)

### test_complete.py (Slower - ~30-60 seconds first run)
- Fetches 3 trackers
- Fetches 3 PRs
- Downloads embedding model (first run only)
- Generates embeddings
- Calculates similarities
- Shows recommendations

## First Run vs Subsequent Runs

### First Run (Slower)
```bash
python test_complete.py
# Downloads model (~90MB) - takes 30-60 seconds
# Then runs test
```

### Subsequent Runs (Fast)
```bash
python test_complete.py
# Uses cached model - takes ~5-10 seconds
```

## Troubleshooting

### "No module named 'dotenv'"
```bash
# Make sure you activated the virtual environment
source venv/bin/activate

# Then install dependencies
pip install -r requirements.txt
```

### "Rate limit exceeded"
```bash
# Add a GitHub token to .env
GITHUB_TOKEN=your_token_here

# Or wait an hour (60 requests/hour without token)
```

### "No trackers/PRs found"
This is normal! It means:
- All trackers already have GitHub links, OR
- All PRs already have tracker references, OR
- API is temporarily unavailable

The code handles this gracefully.

## Testing Without Internet

After first run (model downloaded):
```bash
# You can test embeddings offline
python -c "
from embeddings import SentenceTransformerEmbedder
embedder = SentenceTransformerEmbedder()
embedding = embedder.generate_embedding('test text')
print(f'Embedding shape: {embedding.shape}')
"
```

## Recommended Testing Flow

### Day 1: Basic Setup
```bash
cd python_service
./setup.sh
source venv/bin/activate
cp .env.example .env
python test_scrapers.py  # Quick test
```

### Day 2: Full Pipeline
```bash
source venv/bin/activate
python test_complete.py  # Full test with embeddings
```

### Day 3: Custom Testing
```python
# Create your own test script
from scrapers import CephTrackerScraper
from embeddings import SentenceTransformerEmbedder

# Fetch just 2 trackers
with CephTrackerScraper() as scraper:
    trackers = scraper.fetch_unlinked_trackers(limit=2)
    print(f"Found {len(trackers)} trackers")

# Generate embeddings
embedder = SentenceTransformerEmbedder()
for tracker in trackers:
    embedding = embedder.generate_embedding(tracker['combined_text'])
    print(f"Tracker {tracker['id']}: embedding shape {embedding.shape}")
```

## Summary

✅ **DO**: Copy `.env.example` to `.env`, then edit `.env`
✅ **DO**: Use the provided test scripts (already limited)
✅ **DO**: Start with `test_scrapers.py` (faster)
✅ **DO**: Add GitHub token for better rate limits

❌ **DON'T**: Edit `.env.example` directly
❌ **DON'T**: Worry about scraping too much (limits built-in)
❌ **DON'T**: Need Watsonx API key (using Sentence Transformers)

## Quick Reference

```bash
# Setup
cd python_service && ./setup.sh && source venv/bin/activate

# Configure
cp .env.example .env && nano .env

# Test (fast)
python test_scrapers.py

# Test (complete)
python test_complete.py
```

That's it! 🚀