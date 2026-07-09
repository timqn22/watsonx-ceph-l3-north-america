# Ceph Issue Semantic Search

A powerful tool to scrape issues from the Ceph Redmine tracker and perform semantic similarity searches using local embeddings and vector databases.

## Features

- 🔍 **Scrape Ceph Issues**: Fetch issues from tracker.ceph.com using the Redmine REST API
- 🧠 **Semantic Search**: Find similar issues using state-of-the-art sentence embeddings
- 💾 **Local Vector Database**: Store and query issues using ChromaDB
- 🚀 **No API Keys Required**: Uses open-source sentence-transformers models locally
- 📊 **Rich Metadata**: Preserve issue details, status, priority, and more
- 🔄 **Incremental Updates**: Update individual issues without re-scraping everything
- 🎯 **Flexible Filtering**: Filter by status, priority, project, and more

## Architecture

```
┌─────────────────┐
│  Redmine API    │
│ (tracker.ceph)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Redmine Scraper │
│  (REST Client)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Pipeline      │
│ (Orchestrator)  │
└────────┬────────┘
         │
         ├──────────────────┐
         ▼                  ▼
┌─────────────────┐  ┌──────────────────┐
│ Sentence        │  │   ChromaDB       │
│ Transformers    │  │ (Vector Store)   │
│ (Embeddings)    │  │                  │
└─────────────────┘  └──────────────────┘
         │                  │
         └────────┬─────────┘
                  ▼
         ┌─────────────────┐
         │   CLI / API     │
         │  (User Interface)│
         └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/timqn22/watsonx-ceph-l3-north-america.git
cd watsonx-ceph-l3-north-america
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment (optional):
```bash
cp .env.example .env
# Edit .env with your preferences
```

## Quick Start

### 1. Scrape Issues

Scrape the first 1000 issues from Ceph tracker:

```bash
python cli.py scrape --max-issues 1000
```

This will:
- Fetch issues from tracker.ceph.com
- Generate embeddings using sentence-transformers
- Store them in a local ChromaDB database
- Save raw JSON files for backup

### 2. Search for Similar Issues

Search for issues related to "OSD crash":

```bash
python cli.py search "OSD crash on startup"
```

Output:
```
🔍 Search results for: 'OSD crash on startup'

1. Issue #12345 (similarity: 0.892)
   Subject: OSD crashes immediately after start
   Status: Open | Priority: High
   URL: https://tracker.ceph.com/issues/12345

2. Issue #12346 (similarity: 0.856)
   Subject: Segmentation fault in OSD daemon
   Status: Closed | Priority: Critical
   URL: https://tracker.ceph.com/issues/12346
...
```

### 3. Find Similar Issues

Find issues similar to a specific issue:

```bash
python cli.py similar 12345
```

## Usage

### CLI Commands

#### `scrape` - Scrape issues from Redmine

```bash
python cli.py scrape [OPTIONS]

Options:
  --max-issues INTEGER    Maximum number of issues to scrape (default: all)
  --batch-size INTEGER    Number of issues per batch (default: 100)
  --delay FLOAT          Delay between API requests in seconds (default: 0.5)
  --no-save-raw          Do not save raw JSON files
  --status TEXT          Filter by status (* for all, "open", "closed", or ID)
  --project TEXT         Filter by project ID or identifier
```

Examples:
```bash
# Scrape all open issues
python cli.py scrape --status open

# Scrape first 500 issues with faster rate
python cli.py scrape --max-issues 500 --delay 0.2

# Scrape issues from a specific project
python cli.py scrape --project ceph
```

#### `search` - Search for similar issues

```bash
python cli.py search QUERY [OPTIONS]

Options:
  -n, --limit INTEGER    Number of results to return (default: 10)
  --status TEXT         Filter by status
  --priority TEXT       Filter by priority
  --json-output         Output results as JSON
```

Examples:
```bash
# Basic search
python cli.py search "memory leak in monitor"

# Search with filters
python cli.py search "RGW performance" --status open --limit 5

# Get JSON output
python cli.py search "BlueStore corruption" --json-output
```

#### `similar` - Find issues similar to a specific issue

```bash
python cli.py similar ISSUE_ID [OPTIONS]

Options:
  -n, --limit INTEGER    Number of results to return (default: 10)
  --json-output         Output results as JSON
```

Examples:
```bash
# Find similar issues
python cli.py similar 12345

# Get more results
python cli.py similar 12345 --limit 20
```

#### `update` - Update a specific issue

```bash
python cli.py update ISSUE_ID
```

Example:
```bash
python cli.py update 12345
```

#### `fetch` - Fetch and display an issue

```bash
python cli.py fetch ISSUE_ID [OPTIONS]

Options:
  --include-journals    Include issue journals/comments
```

Examples:
```bash
# Fetch basic issue info
python cli.py fetch 12345

# Fetch with comments
python cli.py fetch 12345 --include-journals
```

#### `stats` - Display database statistics

```bash
python cli.py stats
```

Output:
```
📊 Vector Database Statistics
  - Total issues: 1000
  - Collection name: ceph_issues
  - Persist directory: ./chroma_db
  - Embedding model: all-MiniLM-L6-v2
  - Embedding dimension: 384
```

#### `reset` - Reset the database

```bash
python cli.py reset
```

⚠️ This will delete all issues from the vector database!

## Configuration

Configuration is done via environment variables. Copy `.env.example` to `.env` and customize:

```bash
# Redmine API Configuration
REDMINE_URL=https://tracker.ceph.com
REDMINE_API_KEY=your_api_key_here_optional

# Database Configuration
CHROMA_PERSIST_DIR=./chroma_db
COLLECTION_NAME=ceph_issues

# Scraper Configuration
BATCH_SIZE=100
MAX_ISSUES=10000

# Embedding Model (local, no API key needed)
# Options: all-MiniLM-L6-v2 (fast), all-mpnet-base-v2 (better quality)
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Embedding Models

The system uses sentence-transformers models that run locally without API keys:

| Model | Dimensions | Speed | Quality | Use Case |
|-------|-----------|-------|---------|----------|
| `all-MiniLM-L6-v2` | 384 | Fast | Good | Default, balanced |
| `all-mpnet-base-v2` | 768 | Slower | Better | Higher quality results |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | Fast | Good | Multilingual support |

## Python API

You can also use the library programmatically:

```python
from src.pipeline import IssuePipeline

# Initialize pipeline
pipeline = IssuePipeline(
    redmine_url="https://tracker.ceph.com",
    persist_directory="./chroma_db",
    embedding_model="all-MiniLM-L6-v2"
)

# Scrape and index issues
stats = pipeline.scrape_and_index(
    max_issues=1000,
    batch_size=100,
    delay=0.5
)

# Search for similar issues
results = pipeline.search_similar_issues(
    query="OSD crash on startup",
    n_results=10
)

for result in results:
    print(f"Issue #{result['issue_id']}: {result['metadata']['subject']}")
    print(f"Similarity: {result['similarity_score']:.3f}")

# Find similar issues to a specific issue
similar = pipeline.find_similar_to_issue(
    issue_id="12345",
    n_results=10
)
```

## Advanced Usage

### Custom Filters

You can filter issues during scraping:

```python
from src.redmine_scraper import RedmineScraper

scraper = RedmineScraper()

# Scrape only high priority bugs
for issue in scraper.scrape_all_issues(
    tracker_id=1,  # Bug tracker
    priority_id=5,  # High priority
    status_id='open'
):
    print(f"Issue #{issue['id']}: {issue['subject']}")
```

### Batch Processing

Process issues in batches for better performance:

```python
from src.vector_store import VectorStore

store = VectorStore()

# Prepare batches
issue_ids = []
texts = []
metadatas = []

for issue in issues:
    issue_ids.append(str(issue['id']))
    texts.append(format_issue(issue))
    metadatas.append(extract_metadata(issue))
    
    # Process in batches of 100
    if len(issue_ids) >= 100:
        store.add_issues_batch(issue_ids, texts, metadatas)
        issue_ids = []
        texts = []
        metadatas = []
```

### Metadata Filtering

Filter search results by metadata:

```python
# Search only in open issues
results = store.search(
    query="memory leak",
    n_results=10,
    where={"status": "open"}
)

# Search high priority issues
results = store.search(
    query="crash",
    n_results=10,
    where={"priority": "high"}
)
```

## Project Structure

```
watsonx-ceph-l3-north-america/
├── src/
│   ├── __init__.py
│   ├── redmine_scraper.py    # Redmine API client
│   ├── vector_store.py       # ChromaDB wrapper
│   └── pipeline.py           # Main orchestration
├── cli.py                    # Command-line interface
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
├── README.md                # This file
└── chroma_db/               # Vector database (created on first run)
```

## Troubleshooting

### Issue: "403 Forbidden" when accessing Redmine

Some Redmine instances require authentication. Set your API key:

```bash
export REDMINE_API_KEY=your_api_key_here
```

Or add it to your `.env` file.

### Issue: Out of memory during scraping

Reduce the batch size:

```bash
python cli.py scrape --batch-size 50
```

### Issue: Slow embedding generation

Use a faster model:

```bash
export EMBEDDING_MODEL=all-MiniLM-L6-v2
```

Or reduce the number of issues:

```bash
python cli.py scrape --max-issues 1000
```

## Performance

- **Scraping**: ~100-200 issues/minute (with rate limiting)
- **Embedding**: ~1000 issues/minute on CPU (all-MiniLM-L6-v2)
- **Search**: <100ms for 10 results from 10,000 issues

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- [Ceph Project](https://ceph.io/) - Distributed storage system
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Sentence Transformers](https://www.sbert.net/) - Embedding models
- [Redmine](https://www.redmine.org/) - Issue tracking system

## Support

For issues and questions:
- Open an issue on GitHub
- Check the Ceph documentation: https://docs.ceph.com/
- Visit the Ceph tracker: https://tracker.ceph.com/
