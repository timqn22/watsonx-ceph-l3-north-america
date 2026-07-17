# GitHub PR Monitoring Server Guide

A continuous background service that automatically monitors GitHub PRs and finds similar Redmine issues.

## Overview

The PR Monitor Server runs as a Flask-based web service that:
- ✅ Monitors ceph/ceph GitHub repository continuously
- ✅ Automatically finds similar Redmine issues for new PRs
- ✅ Provides REST API for control and status
- ✅ Saves results to JSON file
- ✅ Tracks processed PRs to avoid duplicates
- ✅ Runs in the background like a daemon

## Quick Start

### 1. Start the Server (Auto-Start Monitoring)

```bash
cd watsonx-ceph-l3-north-america
python3 pr_monitor_server.py --autostart
```

This will:
- Start the Flask server on port 8001
- Automatically begin monitoring PRs every 15 minutes
- Run continuously in the background

### 2. Start Server Without Auto-Start

```bash
python3 pr_monitor_server.py
```

Then start monitoring via API:
```bash
curl -X POST http://localhost:8001/start
```

## Server Options

```bash
# Custom port
python3 pr_monitor_server.py --port 8002

# Custom check interval (30 minutes)
python3 pr_monitor_server.py --autostart --interval 30

# Bind to specific host
python3 pr_monitor_server.py --host 127.0.0.1 --port 8001
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8001/health
```

Response:
```json
{
  "status": "healthy",
  "service": "pr-monitor",
  "running": true
}
```

### Get Status
```bash
curl http://localhost:8001/status
```

Response:
```json
{
  "running": true,
  "last_check": "2024-01-15T10:30:00",
  "total_prs_processed": 42,
  "total_links_found": 420,
  "check_interval_minutes": 15,
  "recent_errors": []
}
```

### Start Monitoring
```bash
# Start with default interval (15 minutes)
curl -X POST http://localhost:8001/start

# Start with custom interval
curl -X POST http://localhost:8001/start \
  -H "Content-Type: application/json" \
  -d '{"interval_minutes": 30}'
```

Response:
```json
{
  "success": true,
  "message": "Monitoring started (checking every 15 minutes)",
  "interval_minutes": 15
}
```

### Stop Monitoring
```bash
curl -X POST http://localhost:8001/stop
```

Response:
```json
{
  "success": true,
  "message": "Monitoring stopped"
}
```

### Trigger Immediate Check
```bash
curl -X POST http://localhost:8001/check-now
```

Response:
```json
{
  "success": true,
  "prs_processed": 3,
  "links_found": 30,
  "timestamp": "2024-01-15T10:35:00"
}
```

### Get Results
```bash
# Get all results
curl http://localhost:8001/results

# Get last 10 results
curl "http://localhost:8001/results?limit=10"
```

Response:
```json
{
  "success": true,
  "count": 42,
  "results": [
    {
      "pr": {
        "pr_number": 12345,
        "title": "Fix OSD crash",
        "url": "https://github.com/ceph/ceph/pull/12345",
        "author": "username",
        "created_at": "2024-01-15T10:30:00Z"
      },
      "similar_issues": [
        {
          "issue_id": "78000",
          "similarity_score": 0.892,
          "metadata": {
            "subject": "OSD crashes on startup",
            "status": "Open",
            "url": "https://tracker.ceph.com/issues/78000"
          }
        }
      ]
    }
  ]
}
```

### Get/Update Configuration
```bash
# Get current config
curl http://localhost:8001/config

# Update check interval
curl -X POST http://localhost:8001/config \
  -H "Content-Type: application/json" \
  -d '{"interval_minutes": 20}'
```

## Running as a Background Service

### Option 1: Using nohup (Simple)

```bash
nohup python3 pr_monitor_server.py --autostart > pr_monitor.log 2>&1 &
echo $! > pr_monitor.pid
```

To stop:
```bash
kill $(cat pr_monitor.pid)
```

### Option 2: Using systemd (Production)

Create `/etc/systemd/system/pr-monitor.service`:

```ini
[Unit]
Description=GitHub PR Monitor Service
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/watsonx-ceph-l3-north-america
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 pr_monitor_server.py --autostart --interval 15
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pr-monitor
sudo systemctl start pr-monitor
sudo systemctl status pr-monitor
```

View logs:
```bash
sudo journalctl -u pr-monitor -f
```

### Option 3: Using screen (Development)

```bash
screen -S pr-monitor
python3 pr_monitor_server.py --autostart
# Press Ctrl+A, then D to detach

# Reattach later
screen -r pr-monitor
```

## Configuration

### GitHub Token (Optional but Recommended)

For higher rate limits (5000/hour instead of 60/hour):

```bash
# Add to .env file
echo "GITHUB_TOKEN=your_github_token_here" >> .env
```

Get token at: https://github.com/settings/tokens

Required permissions: `public_repo` (read-only)

### Environment Variables

Create `.env` file:
```bash
# GitHub API
GITHUB_TOKEN=your_token_here

# Redmine API (if needed)
REDMINE_API_KEY=your_key_here

# Embedding model
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
```

## Monitoring and Logs

### View Logs
```bash
# Real-time logs
tail -f pr_monitor.log

# Last 100 lines
tail -n 100 pr_monitor.log

# Search for errors
grep ERROR pr_monitor.log
```

### Check Server Status
```bash
# Is it running?
curl http://localhost:8001/health

# Detailed status
curl http://localhost:8001/status | jq
```

### Monitor Resource Usage
```bash
# Find process
ps aux | grep pr_monitor_server

# Monitor CPU/Memory
top -p $(pgrep -f pr_monitor_server)
```

## Output Files

### `pr_issue_links.json`
Contains all PR-issue mappings:
```json
[
  {
    "pr": {
      "pr_number": 12345,
      "title": "Fix OSD crash on startup",
      "url": "https://github.com/ceph/ceph/pull/12345",
      "author": "username",
      "created_at": "2024-01-15T10:30:00Z",
      "state": "open",
      "labels": ["bug", "osd"]
    },
    "similar_issues": [
      {
        "issue_id": "78000",
        "similarity_score": 0.892,
        "metadata": {
          "subject": "OSD crashes on startup with segmentation fault",
          "status": "Open",
          "priority": "High",
          "url": "https://tracker.ceph.com/issues/78000"
        }
      }
    ],
    "processed_at": "2024-01-15T10:35:00",
    "search_text": "Title: Fix OSD crash on startup\nDescription: ..."
  }
]
```

### `seen_prs.json`
Tracks processed PR numbers to avoid duplicates:
```json
[12345, 12346, 12347]
```

### `pr_monitor.log`
Server logs with timestamps:
```
2024-01-15 10:30:00 - INFO - PR Monitor Server initialized
2024-01-15 10:30:00 - INFO - Starting continuous monitoring...
2024-01-15 10:30:05 - INFO - Found 3 PRs created in the last 15 minutes
2024-01-15 10:30:10 - INFO - Processing PR #12345: Fix OSD crash
2024-01-15 10:30:15 - INFO - Check complete: 3 PRs processed, 30 links found
```

## Troubleshooting

### Server Won't Start
```bash
# Check if port is already in use
lsof -i :8001

# Try different port
python3 pr_monitor_server.py --port 8002
```

### No PRs Being Found
```bash
# Check GitHub API rate limit
curl -H "Authorization: token YOUR_TOKEN" \
  https://api.github.com/rate_limit

# Trigger manual check
curl -X POST http://localhost:8001/check-now
```

### High Memory Usage
```bash
# Restart the service
curl -X POST http://localhost:8001/stop
curl -X POST http://localhost:8001/start
```

### Database Issues
```bash
# Check if ChromaDB is accessible
ls -la chroma_db/

# Verify embeddings are loaded
curl http://localhost:8000/stats  # From API server
```

## Integration Examples

### Slack Notifications
```python
import requests

# Get new results
response = requests.get('http://localhost:8001/results?limit=1')
data = response.json()

if data['success'] and data['results']:
    pr = data['results'][0]['pr']
    issues = data['results'][0]['similar_issues']
    
    # Send to Slack
    slack_msg = f"New PR #{pr['pr_number']}: {pr['title']}\n"
    slack_msg += f"Found {len(issues)} similar issues"
    
    requests.post(SLACK_WEBHOOK_URL, json={'text': slack_msg})
```

### Email Alerts
```python
import smtplib
from email.mime.text import MIMEText

# Check for high-similarity matches
response = requests.get('http://localhost:8001/results?limit=10')
data = response.json()

for result in data['results']:
    for issue in result['similar_issues']:
        if issue['similarity_score'] > 0.9:
            # Send email alert
            msg = MIMEText(f"High similarity match found!")
            # ... send email
```

## Performance Tips

1. **Adjust Check Interval**: Longer intervals = less API calls
   ```bash
   python3 pr_monitor_server.py --autostart --interval 30
   ```

2. **Use GitHub Token**: Increases rate limit from 60 to 5000/hour
   ```bash
   echo "GITHUB_TOKEN=your_token" >> .env
   ```

3. **Monitor During Peak Hours**: More PRs = more matches
   ```bash
   # Check every 10 minutes during work hours
   python3 pr_monitor_server.py --autostart --interval 10
   ```

4. **Limit Results**: Keep JSON file manageable
   ```bash
   # Periodically archive old results
   mv pr_issue_links.json pr_issue_links_$(date +%Y%m%d).json
   ```

## Comparison: Server vs CLI

| Feature | PR Monitor Server | monitor_prs.py CLI |
|---------|------------------|-------------------|
| Runs continuously | ✅ Yes | ❌ No (manual) |
| REST API | ✅ Yes | ❌ No |
| Auto-restart | ✅ Yes | ❌ No |
| Status monitoring | ✅ Yes | ❌ Limited |
| Background service | ✅ Yes | ⚠️ Requires wrapper |
| Easy to integrate | ✅ Yes | ⚠️ Harder |
| Resource usage | ⚠️ Higher | ✅ Lower |
| Setup complexity | ⚠️ More | ✅ Simple |

**Use Server when:**
- You want continuous monitoring
- You need API access
- You're running in production
- You want status/control endpoints

**Use CLI when:**
- You want one-time checks
- You prefer simple scripts
- You're testing/developing
- You want minimal resource usage

## Next Steps

1. **Start the server**: `python3 pr_monitor_server.py --autostart`
2. **Check status**: `curl http://localhost:8001/status`
3. **View results**: `curl http://localhost:8001/results | jq`
4. **Set up systemd**: For production deployment
5. **Add monitoring**: Integrate with your alerting system

## Support

For issues or questions:
- Check logs: `tail -f pr_monitor.log`
- View status: `curl http://localhost:8001/status`
- Manual check: `curl -X POST http://localhost:8001/check-now`