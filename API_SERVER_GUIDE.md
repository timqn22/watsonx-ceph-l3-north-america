# Simple API Server Guide

This is a lightweight HTTP server that lets you search your Ceph issues from any browser or via curl - no fancy UI, just plain text or JSON results.

## Quick Start

```bash
cd watsonx-ceph-l3-north-america
python3 api_server.py
```

The server will start on `http://localhost:8000`

## Usage Examples

### 1. Search from Browser

Open your browser and go to:
```
http://localhost:8000/search?q=OSD+crash
http://localhost:8000/search?q=memory+leak&limit=5
http://localhost:8000/similar/78000
```

### 2. Search with curl

```bash
# Search for issues
curl "http://localhost:8000/search?q=cluster"
curl "http://localhost:8000/search?q=OSD+crash&limit=10"

# Find similar issues
curl "http://localhost:8000/similar/78000?limit=10"

# Get database stats
curl "http://localhost:8000/stats"

# Health check
curl "http://localhost:8000/health"
```

### 3. Get JSON Response

Add `&format=json` to any request:

```bash
curl "http://localhost:8000/search?q=crash&format=json"
curl "http://localhost:8000/similar/78000?format=json"
```

## Access from Other Devices

### Find Your IP Address

**macOS/Linux:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

**Or check System Preferences → Network**

### Access from Another Device

Replace `localhost` with your IP address:
```
http://192.168.1.100:8000/search?q=crash
```

**Note:** Make sure your firewall allows connections on port 8000.

## API Endpoints

| Endpoint | Parameters | Description |
|----------|-----------|-------------|
| `/` | - | Show usage instructions |
| `/search` | `q` (required), `limit`, `format` | Search for issues |
| `/similar/<id>` | `limit`, `format` | Find similar issues |
| `/stats` | `format` | Database statistics |
| `/health` | - | Health check |

## Parameters

- **q**: Search query (required for `/search`)
- **limit**: Number of results (default: 10)
- **format**: Response format - `text` or `json` (default: text)

## Examples

### Search for "cluster" issues
```bash
curl "http://localhost:8000/search?q=cluster"
```

Output:
```
Search Results for: cluster
================================================================================

1. Issue #77999 (similarity: 0.456)
   Subject: umbrella: [test] pin valgrind subsuite to centos_9.stream
   Status: New | Priority: Normal
   URL: https://tracker.ceph.com/issues/77999
   Preview: Subject: umbrella: [test] pin valgrind subsuite to centos_9...

2. Issue #78042 (similarity: 0.423)
   Subject: Linux kernel CephFS client retains ~42M caps during metadata
   Status: New | Priority: Normal
   URL: https://tracker.ceph.com/issues/78042
   Preview: Subject: Linux kernel CephFS client retains ~42M caps...

Total results: 10
```

### Get JSON response
```bash
curl "http://localhost:8000/search?q=crash&limit=3&format=json"
```

Output:
```json
[
  {
    "issue_id": "77993",
    "similarity_score": 0.892,
    "document": "Subject: startup crash due to race...",
    "metadata": {
      "issue_id": "77993",
      "subject": "startup crash due to race between lifecycle and quota handler",
      "status": "Fix Under Review",
      "priority": "Normal",
      "url": "https://tracker.ceph.com/issues/77993"
    }
  }
]
```

## Change Port

Run on a different port:
```bash
python3 api_server.py 9000
```

Then access at `http://localhost:9000`

## Stop the Server

Press `Ctrl+C` in the terminal where the server is running.

## Troubleshooting

### Port already in use
```bash
# Use a different port
python3 api_server.py 9000
```

### Can't access from other devices
- Check your firewall settings
- Make sure you're using your actual IP address, not localhost
- Ensure both devices are on the same network

### Slow first request
The first request loads the embedding model into memory (~30 seconds). Subsequent requests are fast.

## Integration Examples

### Python
```python
import requests

response = requests.get('http://localhost:8000/search', params={
    'q': 'OSD crash',
    'limit': 10,
    'format': 'json'
})
results = response.json()
```

### JavaScript
```javascript
fetch('http://localhost:8000/search?q=crash&format=json')
  .then(response => response.json())
  .then(data => console.log(data));
```

### Shell Script
```bash
#!/bin/bash
QUERY="$1"
curl -s "http://localhost:8000/search?q=${QUERY}&limit=5"
```

## Comparison with CLI

| Feature | CLI | API Server |
|---------|-----|------------|
| Usage | `python3 cli.py search "query"` | `curl "http://localhost:8000/search?q=query"` |
| Access | Local terminal only | Any browser, any device |
| Output | Terminal text | Plain text or JSON |
| Integration | Shell scripts | Any HTTP client |

## Security Note

This server has no authentication. Anyone who can reach your IP address can search your database. For production use, consider:
- Adding authentication
- Using HTTPS
- Restricting access by IP
- Running behind a reverse proxy

## Summary

You now have a simple HTTP API that provides the same functionality as `python3 cli.py search` but accessible from any browser or HTTP client!

```bash
# Start server
python3 api_server.py

# Search from anywhere
curl "http://localhost:8000/search?q=your+query"