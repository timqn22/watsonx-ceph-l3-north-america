# Ceph Tracker Linker REST API Documentation

## Base URL
```
http://localhost:5000
```

## Endpoints

### Health & Status

#### GET /health
Health check endpoint

**Response:**
```json
{
  "status": "ok",
  "service": "ceph-tracker-linker",
  "version": "1.0.0"
}
```

#### GET /status
Detailed status information

**Response:**
```json
{
  "status": "ok",
  "service": "ceph-tracker-linker",
  "version": "1.0.0",
  "embedder": {
    "model_name": "all-MiniLM-L6-v2",
    "embedding_dimension": 384,
    "cache_dir": "./models",
    "max_seq_length": 256
  },
  "similarity_threshold": 0.75,
  "config": {
    "ceph_tracker_url": "https://tracker.ceph.com",
    "github_repo": "ceph/ceph",
    "max_recommendations": 10
  }
}
```

---

### Trackers

#### GET /api/trackers
Get unlinked trackers from Ceph tracker

**Query Parameters:**
- `limit` (int, optional): Maximum number of trackers to return (default: 10)
- `offset` (int, optional): Offset for pagination (default: 0)

**Example:**
```bash
curl "http://localhost:5000/api/trackers?limit=5&offset=0"
```

**Response:**
```json
{
  "success": true,
  "count": 5,
  "trackers": [
    {
      "id": 74827,
      "tracker_id": 74827,
      "subject": "TEST_mon_features fails...",
      "description": "Full description...",
      "status": "Pending Backport",
      "priority": "Normal",
      "author": "Developer Name",
      "created_on": "2024-01-01T00:00:00Z",
      "updated_on": "2024-01-02T00:00:00Z",
      "project": "Ceph",
      "tracker_type": "Bug",
      "url": "https://tracker.ceph.com/issues/74827",
      "combined_text": "Subject and description combined..."
    }
  ]
}
```

#### GET /api/trackers/{tracker_id}
Get specific tracker by ID

**Path Parameters:**
- `tracker_id` (int, required): Tracker ID

**Example:**
```bash
curl "http://localhost:5000/api/trackers/74827"
```

**Response:**
```json
{
  "success": true,
  "tracker": { /* tracker object */ }
}
```

---

### Pull Requests

#### GET /api/prs
Get unlinked pull requests from GitHub

**Query Parameters:**
- `limit` (int, optional): Maximum number of PRs to return (default: 10)
- `state` (string, optional): PR state - 'open', 'closed', or 'all' (default: 'open')

**Example:**
```bash
curl "http://localhost:5000/api/prs?limit=5&state=open"
```

**Response:**
```json
{
  "success": true,
  "count": 5,
  "prs": [
    {
      "id": 123456789,
      "pr_number": 54321,
      "title": "Fix memory leak in OSD",
      "body": "This PR fixes...",
      "state": "open",
      "author": "developer",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-02T00:00:00Z",
      "merged_at": null,
      "labels": ["bug", "osd"],
      "url": "https://github.com/ceph/ceph/pull/54321",
      "api_url": "https://api.github.com/repos/ceph/ceph/pulls/54321",
      "combined_text": "Title and body combined...",
      "additions": 50,
      "deletions": 10,
      "changed_files": 3,
      "commits": 2,
      "mergeable": true,
      "draft": false
    }
  ]
}
```

#### GET /api/prs/{pr_number}
Get specific PR by number

**Path Parameters:**
- `pr_number` (int, required): Pull request number

**Example:**
```bash
curl "http://localhost:5000/api/prs/54321"
```

**Response:**
```json
{
  "success": true,
  "pr": { /* PR object */ }
}
```

---

### Embeddings

#### POST /api/embeddings/generate
Generate embeddings for texts

**Request Body:**
```json
{
  "texts": [
    "Fix memory leak in OSD",
    "Update documentation for RGW"
  ]
}
```

**Example:**
```bash
curl -X POST "http://localhost:5000/api/embeddings/generate" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Fix memory leak", "Update docs"]}'
```

**Response:**
```json
{
  "success": true,
  "count": 2,
  "dimension": 384,
  "embeddings": [
    [0.123, 0.456, ...],  // 384 dimensions
    [0.789, 0.012, ...]   // 384 dimensions
  ]
}
```

---

### Recommendations

#### GET /api/recommendations
Get all recommendations (trackers matched with PRs)

**Query Parameters:**
- `tracker_limit` (int, optional): Max trackers to fetch (default: 10)
- `pr_limit` (int, optional): Max PRs to fetch (default: 50)
- `top_k` (int, optional): Top K matches per tracker (default: 5)

**Example:**
```bash
curl "http://localhost:5000/api/recommendations?tracker_limit=5&pr_limit=20&top_k=3"
```

**Response:**
```json
{
  "success": true,
  "count": 15,
  "recommendations": [
    {
      "tracker": { /* full tracker object */ },
      "pr": { /* full PR object */ },
      "similarity": 0.87,
      "confidence": "high"
    }
  ]
}
```

**Confidence Levels:**
- `very_high`: similarity >= 0.9
- `high`: similarity >= 0.8
- `medium`: similarity >= 0.7
- `low`: similarity < 0.7

#### GET /api/recommendations/tracker/{tracker_id}
Get recommendations for a specific tracker

**Path Parameters:**
- `tracker_id` (int, required): Tracker ID

**Query Parameters:**
- `top_k` (int, optional): Number of top matches (default: 10)
- `pr_limit` (int, optional): Max PRs to search (default: 100)

**Example:**
```bash
curl "http://localhost:5000/api/recommendations/tracker/74827?top_k=5"
```

**Response:**
```json
{
  "success": true,
  "tracker": { /* tracker object */ },
  "count": 5,
  "recommendations": [
    {
      "pr": { /* PR object */ },
      "similarity": 0.92,
      "confidence": "very_high"
    }
  ]
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "success": false,
  "error": "Error message description"
}
```

**HTTP Status Codes:**
- `200`: Success
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (resource doesn't exist)
- `500`: Internal Server Error

---

## Usage Examples

### Python
```python
import requests

# Get recommendations
response = requests.get(
    'http://localhost:5000/api/recommendations',
    params={'tracker_limit': 5, 'pr_limit': 20}
)
data = response.json()

for rec in data['recommendations']:
    print(f"Tracker #{rec['tracker']['tracker_id']}")
    print(f"  → PR #{rec['pr']['pr_number']}")
    print(f"  Similarity: {rec['similarity']:.2f}")
```

### Ruby (for Redmine plugin)
```ruby
require 'net/http'
require 'json'

uri = URI('http://localhost:5000/api/recommendations')
uri.query = URI.encode_www_form(tracker_limit: 5, pr_limit: 20)

response = Net::HTTP.get_response(uri)
data = JSON.parse(response.body)

data['recommendations'].each do |rec|
  puts "Tracker ##{rec['tracker']['tracker_id']}"
  puts "  → PR ##{rec['pr']['pr_number']}"
  puts "  Similarity: #{rec['similarity'].round(2)}"
end
```

### cURL
```bash
# Health check
curl http://localhost:5000/health

# Get trackers
curl "http://localhost:5000/api/trackers?limit=5"

# Get PRs
curl "http://localhost:5000/api/prs?limit=5&state=open"

# Generate embeddings
curl -X POST http://localhost:5000/api/embeddings/generate \
  -H "Content-Type: application/json" \
  -d '{"texts": ["test text"]}'

# Get recommendations
curl "http://localhost:5000/api/recommendations?tracker_limit=3&pr_limit=10"

# Get recommendations for specific tracker
curl "http://localhost:5000/api/recommendations/tracker/74827"
```

---

## Running the API

### Development
```bash
cd python_service
source venv/bin/activate
python api/app.py
```

### Production (with Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

---

## Testing

### Run API tests
```bash
# Terminal 1: Start API
python api/app.py

# Terminal 2: Run tests
python test_api.py
```

### Manual testing
```bash
# Health check
curl http://localhost:5000/health

# Status
curl http://localhost:5000/status
```

---

## Performance Notes

- **First request**: Slower (~30-60s) due to model loading
- **Subsequent requests**: Fast (~1-5s)
- **Embeddings**: Cached after generation
- **Rate limits**: GitHub API limits apply (60/hour without token, 5000/hour with token)

---

## Configuration

Edit `.env` file:
```bash
# Service
HOST=0.0.0.0
PORT=5000
DEBUG=True

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Similarity
SIMILARITY_THRESHOLD=0.75
MAX_RECOMMENDATIONS=10