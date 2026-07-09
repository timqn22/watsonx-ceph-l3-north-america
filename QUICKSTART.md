# Quick Start Guide - RAG on First 100 Ceph Issues

This guide will get you up and running with semantic search on Ceph issues in under 5 minutes.

## Step 1: Install Dependencies

```bash
cd watsonx-ceph-l3-north-america
pip install -r requirements.txt
```

This will install:
- `requests` - For API calls
- `chromadb` - Vector database
- `sentence-transformers` - Local embeddings (no API key needed!)
- `click` - CLI framework
- Other utilities

## Step 2: Scrape First 100 Issues

Run this command to scrape and index the first 100 issues:

```bash
python3 cli.py scrape --max-issues 100
```

This will:
1. Fetch 100 issues from tracker.ceph.com
2. Generate embeddings using a local AI model
3. Store them in a vector database (`./chroma_db/`)
4. Save raw JSON files for backup (`./raw_issues/`)

**Expected output:**
```
🔍 Starting Ceph issue scraping...
Scraping issues: 100%|████████████| 100/100 [00:45<00:00,  2.21it/s]

✅ Scraping complete!
📊 Statistics:
  - Total scraped: 100
  - Total indexed: 100
  - Errors: 0
  - Vector store count: 100
```

**Time:** ~1-2 minutes (depending on your internet speed)

## Step 3: Search for Similar Issues (RAG)

Now you can perform semantic searches! The system uses RAG (Retrieval-Augmented Generation) to find similar issues.

### Example 1: Search by Description

```bash
python cli.py search "OSD crashes on startup with segmentation fault"
```

**Output:**
```
🔍 Search results for: 'OSD crashes on startup with segmentation fault'

1. Issue #12345 (similarity: 0.892)
   Subject: OSD daemon crashes immediately after start
   Status: Open | Priority: High
   URL: https://tracker.ceph.com/issues/12345

2. Issue #12346 (similarity: 0.856)
   Subject: Segmentation fault in OSD process
   Status: Closed | Priority: Critical
   URL: https://tracker.ceph.com/issues/12346

3. Issue #12347 (similarity: 0.834)
   Subject: OSD fails to initialize on boot
   Status: Open | Priority: Medium
   URL: https://tracker.ceph.com/issues/12347
...
```

### Example 2: Search for Performance Issues

```bash
python cli.py search "slow performance degradation over time" --limit 5
```

### Example 3: Search with Filters

```bash
# Only search open issues
python cli.py search "memory leak" --status open

# Only high priority issues
python cli.py search "data corruption" --priority high
```

### Example 4: Find Similar Issues to a Specific Issue

```bash
python cli.py similar 45 --limit 10
```

This finds issues similar to issue #45.

## Step 4: Get More Results

Want to search more issues? Just scrape more:

```bash
# Scrape 1000 issues
python cli.py scrape --max-issues 1000

# Scrape all issues (this will take a while!)
python cli.py scrape
```

## How RAG Works Here

This system implements RAG (Retrieval-Augmented Generation) for semantic search:

1. **Retrieval**: When you search, your query is converted to an embedding vector
2. **Augmentation**: The system finds the most similar issue embeddings in the database
3. **Generation**: Results are ranked by similarity score and returned with full metadata

**Key Features:**
- ✅ **Semantic Understanding**: Finds issues with similar meaning, not just keyword matches
- ✅ **Fast**: Sub-second search on thousands of issues
- ✅ **Local**: No API keys needed, runs entirely on your machine
- ✅ **Accurate**: Uses state-of-the-art sentence-transformers models

## Common Use Cases

### 1. Find Duplicate Issues
```bash
python cli.py similar 12345
```

### 2. Research a Problem
```bash
python cli.py search "RGW returns 500 errors intermittently"
```

### 3. Track Related Issues
```bash
python cli.py search "BlueStore performance" --status open --limit 20
```

### 4. Get Issue Details
```bash
python cli.py fetch 12345 --include-journals
```

### 5. Check Database Stats
```bash
python cli.py stats
```

**Output:**
```
📊 Vector Database Statistics
  - Total issues: 100
  - Collection name: ceph_issues
  - Persist directory: ./chroma_db
  - Embedding model: all-MiniLM-L6-v2
  - Embedding dimension: 384
```

## Python API Usage

You can also use the Python API directly:

```python
from src.pipeline import IssuePipeline

# Initialize
pipeline = IssuePipeline()

# Scrape and index
stats = pipeline.scrape_and_index(max_issues=100)
print(f"Indexed {stats['total_indexed']} issues")

# Search (RAG)
results = pipeline.search_similar_issues(
    query="OSD crash on startup",
    n_results=10
)

# Print results
for result in results:
    print(f"Issue #{result['issue_id']}: {result['metadata']['subject']}")
    print(f"Similarity: {result['similarity_score']:.3f}")
    print(f"URL: {result['metadata']['url']}\n")
```

## Advanced: Using Different Embedding Models

For better quality (but slower):

```bash
# Create .env file
echo "EMBEDDING_MODEL=all-mpnet-base-v2" > .env

# Scrape with better model
python cli.py scrape --max-issues 100
```

## Troubleshooting

### "Module not found" error
```bash
pip install -r requirements.txt
```

### Slow scraping
```bash
# Reduce delay between requests
python cli.py scrape --max-issues 100 --delay 0.2
```

### Out of memory
```bash
# Use smaller batches
python cli.py scrape --max-issues 100 --batch-size 25
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [examples/basic_usage.py](examples/basic_usage.py) for code examples
- Run `python cli.py --help` to see all commands

## Summary

You now have a working RAG system for Ceph issues! 🎉

**What you can do:**
- ✅ Semantic search across issues
- ✅ Find similar/duplicate issues
- ✅ Filter by status, priority, etc.
- ✅ All running locally with no API keys

**Commands to remember:**
```bash
python cli.py scrape --max-issues 100    # Index issues
python cli.py search "your query"        # Search
python cli.py similar 12345              # Find similar
python cli.py stats                      # Check status