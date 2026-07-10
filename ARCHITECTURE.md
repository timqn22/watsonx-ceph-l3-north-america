# Ceph Tracker Linker - Architecture Document

## Overview

The Ceph Tracker Linker uses a **hybrid microservice architecture** combining Python and Ruby to leverage the strengths of each language.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         Redmine UI                          │
│                    (Ruby on Rails)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTP/REST
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Ruby Redmine Plugin                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Controllers (Display, User Actions)                 │  │
│  │  Models (Cache, Database)                            │  │
│  │  Views (UI Templates)                                │  │
│  │  Python Service Client (HTTP Client)                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ REST API
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Python Microservice                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Flask REST API                                      │  │
│  │  ├─ /api/trackers                                    │  │
│  │  ├─ /api/prs                                         │  │
│  │  ├─ /api/embeddings                                  │  │
│  │  └─ /api/recommendations                             │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Business Logic                                      │  │
│  │  ├─ Scrapers (Ceph Tracker, GitHub)                 │  │
│  │  ├─ Embeddings (Watsonx Granite)                    │  │
│  │  ├─ Similarity Calculator                           │  │
│  │  └─ Recommendation Engine                           │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Data Layer                                          │  │
│  │  ├─ Redis Cache                                      │  │
│  │  └─ SQLite/PostgreSQL (optional)                    │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Ceph      │  │   GitHub    │  │  Watsonx    │
│  Tracker    │  │     API     │  │     AI      │
└─────────────┘  └─────────────┘  └─────────────┘
```

## Component Breakdown

### 1. Python Microservice (Core Engine)

**Purpose**: Heavy computational tasks, AI/ML operations, external API interactions

**Responsibilities**:
- Scrape data from Ceph tracker and GitHub
- Generate embeddings using Watsonx Granite models
- Calculate similarity scores
- Produce recommendations
- Expose REST API

**Technology Stack**:
- **Flask**: Web framework for REST API
- **Requests**: HTTP client for external APIs
- **PyGithub**: GitHub API client
- **ibm-watsonx-ai**: Watsonx SDK for embeddings
- **NumPy/scikit-learn**: Similarity calculations
- **Redis**: Caching layer

**Key Files**:
```
python_service/
├── api/app.py                    # Flask application
├── scrapers/
│   ├── ceph_tracker_scraper.py  # Ceph tracker scraper
│   └── github_pr_scraper.py     # GitHub PR scraper
├── embeddings/
│   └── watsonx_embedder.py      # Embedding generation
├── similarity/
│   └── calculator.py            # Similarity calculation
└── recommendations/
    └── engine.py                # Recommendation logic
```

### 2. Ruby Redmine Plugin (Integration Layer)

**Purpose**: Redmine integration, UI, user interaction

**Responsibilities**:
- Display recommendations in Redmine UI
- Handle user actions (approve/reject links)
- Cache results in Redmine database
- Call Python service via HTTP
- Manage plugin configuration

**Technology Stack**:
- **Ruby on Rails**: Redmine framework
- **HTTParty**: HTTP client for Python service
- **ActiveRecord**: Database ORM

**Key Files**:
```
redmine_plugin/
├── init.rb                      # Plugin initialization
├── lib/
│   └── python_service_client.rb # HTTP client
├── app/
│   ├── controllers/
│   │   └── ceph_tracker_linker_controller.rb
│   ├── models/
│   │   └── linkage_recommendation.rb
│   └── views/
│       └── ceph_tracker_linker/
└── config/
    └── routes.rb
```

## Data Flow

### 1. Scraping Flow

```
User triggers scan
    ↓
Ruby Plugin → Python API (/api/scan)
    ↓
Python Service:
    ├─ Scrape Ceph Tracker
    ├─ Scrape GitHub PRs
    ├─ Filter unlinked items
    └─ Return data
    ↓
Ruby Plugin caches results
    ↓
Display in Redmine UI
```

### 2. Embedding Generation Flow

```
New tracker/PR detected
    ↓
Python Service:
    ├─ Check cache (Redis)
    ├─ If not cached:
    │   ├─ Extract text
    │   ├─ Call Watsonx API
    │   ├─ Generate embedding
    │   └─ Cache result
    └─ Return embedding
```

### 3. Recommendation Flow

```
User requests recommendations
    ↓
Ruby Plugin → Python API (/api/recommendations)
    ↓
Python Service:
    ├─ Get all unlinked trackers
    ├─ Get all unlinked PRs
    ├─ Generate embeddings (if needed)
    ├─ Calculate similarities
    ├─ Rank by score
    ├─ Filter by threshold
    └─ Return top N recommendations
    ↓
Ruby Plugin:
    ├─ Cache recommendations
    ├─ Store in database
    └─ Display in UI
```

## API Specification

### Python Service REST API

#### Scrapers

**GET /api/trackers**
- Fetch unlinked trackers
- Query params: `limit`, `offset`, `project_id`
- Returns: Array of tracker objects

**GET /api/prs**
- Fetch unlinked PRs
- Query params: `limit`, `offset`, `state`
- Returns: Array of PR objects

#### Embeddings

**POST /api/embeddings/generate**
- Generate embeddings for text
- Body: `{ "texts": ["text1", "text2"] }`
- Returns: Array of embedding vectors

**GET /api/embeddings/tracker/{id}**
- Get cached embedding for tracker
- Returns: Embedding vector or 404

#### Recommendations

**GET /api/recommendations**
- Get all recommendations
- Query params: `threshold`, `limit`
- Returns: Array of recommendation objects

**GET /api/recommendations/tracker/{id}**
- Get recommendations for specific tracker
- Returns: Array of matching PRs with scores

#### Health

**GET /api/health**
- Service health check
- Returns: `{ "status": "ok", "version": "1.0.0" }`

**GET /api/status**
- Detailed status
- Returns: Service metrics, cache status, API limits

## Design Decisions

### Why Python for Core Logic?

1. **Better ML/AI Libraries**: NumPy, scikit-learn, TensorFlow ecosystem
2. **Watsonx SDK**: Official Python SDK with better support
3. **Data Processing**: Pandas, NumPy for efficient data manipulation
4. **Async Support**: Better async/await for concurrent API calls
5. **Type Hints**: Better code documentation and IDE support

### Why Ruby for Redmine Integration?

1. **Native Integration**: Redmine is built in Ruby on Rails
2. **Direct Database Access**: ActiveRecord models
3. **UI Framework**: Rails views and helpers
4. **Plugin System**: Redmine's plugin architecture is Ruby-based
5. **Existing Ecosystem**: Leverage Redmine's authentication, permissions

### Why Microservice Architecture?

1. **Separation of Concerns**: Clear boundaries between components
2. **Independent Scaling**: Scale Python service separately
3. **Technology Choice**: Use best tool for each job
4. **Independent Deployment**: Update Python service without Redmine restart
5. **Testability**: Test components independently

## Communication Protocol

### HTTP/REST

- **Protocol**: HTTP/1.1 with JSON payloads
- **Authentication**: API key in header (future)
- **Error Handling**: Standard HTTP status codes
- **Timeout**: 30 seconds default
- **Retry Logic**: Exponential backoff

### Data Format

```json
{
  "tracker": {
    "id": 12345,
    "subject": "Memory leak in OSD",
    "description": "...",
    "combined_text": "...",
    "embedding": [0.1, 0.2, ...]
  },
  "pr": {
    "number": 54321,
    "title": "Fix memory leak",
    "body": "...",
    "combined_text": "...",
    "embedding": [0.15, 0.25, ...]
  },
  "similarity": 0.87,
  "confidence": "high"
}
```

## Caching Strategy

### Redis Cache

**Purpose**: Store embeddings, API responses, rate limit counters

**Key Patterns**:
- `embedding:tracker:{id}` - Tracker embeddings
- `embedding:pr:{number}` - PR embeddings
- `recommendations:tracker:{id}` - Cached recommendations
- `ratelimit:{client_id}` - Rate limit counters

**TTL**:
- Embeddings: 24 hours
- Recommendations: 1 hour
- Rate limits: 1 minute

### Database Cache (Redmine)

**Purpose**: Persistent storage of recommendations, user actions

**Tables**:
- `linkage_recommendations` - Recommendation history
- `user_actions` - Approve/reject actions
- `embedding_cache` - Long-term embedding storage

## Security Considerations

### API Security

1. **Authentication**: API key required for Python service
2. **Rate Limiting**: Per-client rate limits
3. **Input Validation**: Sanitize all inputs
4. **CORS**: Restrict to Redmine domain
5. **HTTPS**: Enforce TLS in production

### Data Privacy

1. **No PII Storage**: Don't store personal information
2. **Audit Logging**: Log all user actions
3. **Access Control**: Redmine permissions apply
4. **API Key Rotation**: Regular key rotation

## Performance Optimization

### Caching

- Cache embeddings (expensive to generate)
- Cache API responses (reduce external calls)
- Cache recommendations (reduce computation)

### Batch Processing

- Batch embedding generation
- Batch similarity calculations
- Async scraping

### Database Optimization

- Index frequently queried fields
- Use connection pooling
- Optimize queries

## Monitoring & Logging

### Metrics to Track

- API response times
- Embedding generation time
- Cache hit/miss rates
- External API rate limits
- Error rates
- Recommendation accuracy

### Logging

- Structured logging (JSON)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Centralized logging (future)

## Deployment

### Development

```bash
# Python service
cd python_service
source venv/bin/activate
python api/app.py

# Redmine (separate terminal)
cd /path/to/redmine
bundle exec rails server
```

### Production

```bash
# Python service (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app

# Redmine (with passenger/puma)
# Standard Redmine deployment
```

### Docker (Future)

```yaml
version: '3.8'
services:
  python-service:
    build: ./python_service
    ports:
      - "5000:5000"
    environment:
      - WATSONX_API_KEY=${WATSONX_API_KEY}
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  redmine:
    image: redmine:5
    ports:
      - "3000:3000"
    depends_on:
      - python-service
```

## Future Enhancements

1. **Async Processing**: Background jobs for scraping
2. **WebSocket**: Real-time updates
3. **GraphQL**: More flexible API
4. **Machine Learning**: Improve recommendations over time
5. **Multi-tenancy**: Support multiple Redmine instances
6. **Analytics Dashboard**: Visualize recommendation accuracy