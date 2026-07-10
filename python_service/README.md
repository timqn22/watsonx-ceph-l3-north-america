# Ceph Tracker Linker - Python Service

Python microservice for scraping, embedding, and recommending linkages between Ceph trackers and GitHub PRs.

## Architecture

This service handles the heavy lifting:
- **Scraping**: Fetches data from Ceph tracker and GitHub
- **Embedding**: Generates embeddings using IBM Watsonx Granite models
- **Similarity**: Calculates similarity scores between trackers and PRs
- **Recommendations**: Produces ranked linkage recommendations
- **REST API**: Exposes endpoints for the Redmine plugin to consume

## Project Structure

```
python_service/
├── config.py                    # Configuration management
├── requirements.txt             # Python dependencies
├── setup.sh                     # Setup script
├── test_scrapers.py            # Manual test script
├── .env.example                # Environment template
├── scrapers/
│   ├── __init__.py
│   ├── ceph_tracker_scraper.py # Ceph tracker scraper
│   └── github_pr_scraper.py    # GitHub PR scraper
├── embeddings/                  # Embedding generation (TODO)
│   ├── __init__.py
│   └── watsonx_embedder.py
├── similarity/                  # Similarity calculation (TODO)
│   ├── __init__.py
│   └── calculator.py
├── api/                        # Flask REST API (TODO)
│   ├── __init__.py
│   ├── app.py
│   └── routes/
└── tests/                      # Unit tests
    ├── test_ceph_scraper.py
    └── test_github_scraper.py
```

## Installation

### Quick Setup

```bash
cd python_service
./setup.sh
```

### Manual Setup

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

Edit `.env` file with your credentials:

```bash
# Required
GITHUB_TOKEN=your_github_token
WATSONX_API_KEY=your_watsonx_api_key
WATSONX_PROJECT_ID=your_project_id

# Optional
CEPH_TRACKER_URL=https://tracker.ceph.com
GITHUB_REPO=ceph/ceph
SIMILARITY_THRESHOLD=0.75
MAX_RECOMMENDATIONS=10
```

## Usage

### Test Scrapers

```bash
# Activate virtual environment
source venv/bin/activate

# Run test script
python test_scrapers.py
```

### Run Unit Tests

```bash
pytest tests/ -v
```

### Start API Service (when ready)

```bash
python api/app.py
```

## API Endpoints (Planned)

### Scrapers
- `GET /api/trackers` - Fetch unlinked trackers
- `GET /api/trackers/{id}` - Get specific tracker
- `GET /api/prs` - Fetch unlinked PRs
- `GET /api/prs/{number}` - Get specific PR

### Embeddings
- `POST /api/embeddings/generate` - Generate embeddings
- `GET /api/embeddings/tracker/{id}` - Get tracker embedding
- `GET /api/embeddings/pr/{number}` - Get PR embedding

### Recommendations
- `GET /api/recommendations` - Get all recommendations
- `GET /api/recommendations/tracker/{id}` - Get recommendations for tracker
- `POST /api/recommendations/refresh` - Refresh recommendations

### Health
- `GET /api/health` - Service health check
- `GET /api/status` - Detailed status

## Development

### Stage 1: Scrapers ✅

**Status**: Complete

**Files**:
- `scrapers/ceph_tracker_scraper.py` (211 lines)
- `scrapers/github_pr_scraper.py` (280 lines)
- `test_scrapers.py` (145 lines)

**Features**:
- Fetch unlinked trackers and PRs
- Filter already-linked items
- Search functionality
- Rate limit handling
- Standardized data format

### Stage 2: Embeddings (Next)

**TODO**:
- Implement Watsonx embedding generator
- Add caching layer
- Batch processing
- Error handling

**Files to Create**:
- `embeddings/watsonx_embedder.py`
- `embeddings/cache.py`
- `tests/test_embedder.py`

### Stage 3: Similarity & Recommendations

**TODO**:
- Cosine similarity calculator
- Recommendation engine
- Ranking algorithm
- Threshold filtering

### Stage 4: REST API

**TODO**:
- Flask application
- API routes
- Authentication
- Rate limiting
- Documentation (Swagger)

## Testing

### Manual Testing

```bash
# Test Ceph tracker scraper
python -c "
from scrapers import CephTrackerScraper
scraper = CephTrackerScraper()
trackers = scraper.fetch_unlinked_trackers(limit=5)
print(f'Found {len(trackers)} trackers')
"

# Test GitHub PR scraper
python -c "
from scrapers import GithubPRScraper
import os
scraper = GithubPRScraper(access_token=os.getenv('GITHUB_TOKEN'))
prs = scraper.fetch_unlinked_prs(limit=5)
print(f'Found {len(prs)} PRs')
"
```

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=scrapers --cov-report=html

# Run specific test
pytest tests/test_ceph_scraper.py -v
```

## Dependencies

### Core
- `flask` - Web framework
- `requests` - HTTP client
- `PyGithub` - GitHub API client
- `ibm-watsonx-ai` - Watsonx SDK

### Data Processing
- `numpy` - Numerical computing
- `pandas` - Data manipulation
- `scikit-learn` - ML utilities
- `scipy` - Scientific computing

### Development
- `pytest` - Testing framework
- `black` - Code formatter
- `flake8` - Linter
- `mypy` - Type checker

## Troubleshooting

### Import Errors

If you see import errors, ensure virtual environment is activated:
```bash
source venv/bin/activate
```

### GitHub Rate Limits

Without authentication: 60 requests/hour
With token: 5000 requests/hour

Check rate limit:
```python
from scrapers import GithubPRScraper
scraper = GithubPRScraper(access_token='your_token')
print(scraper.get_rate_limit_status())
```

### Watsonx Connection Issues

Verify credentials:
```bash
echo $WATSONX_API_KEY
echo $WATSONX_PROJECT_ID
```

Test connection (when embedder is implemented):
```python
from embeddings import WatsonxEmbedder
embedder = WatsonxEmbedder()
# Test embedding generation
```

## Performance Considerations

### Caching
- Redis for embedding cache
- TTL: 1 hour (configurable)
- Cache key format: `embedding:{type}:{id}`

### Rate Limiting
- GitHub: Respect rate limits
- Watsonx: Batch requests when possible
- API: Rate limit per client

### Optimization
- Batch embedding generation
- Async scraping (future)
- Database indexing
- Connection pooling

## Security

### API Keys
- Never commit `.env` file
- Use environment variables
- Rotate keys regularly

### API Security
- Authentication required
- Rate limiting enabled
- Input validation
- CORS configuration

## Contributing

1. Create feature branch
2. Write tests
3. Follow code style (black, flake8)
4. Update documentation
5. Submit pull request

## License

[Your License]

## Support

For issues or questions:
- GitHub Issues: [repository-url]
- Documentation: [docs-url]