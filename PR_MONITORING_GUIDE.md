# GitHub PR Monitoring Guide

Automatically monitor Ceph GitHub PRs and find similar Redmine issues using semantic search.

## Features

- 🔄 **Continuous Monitoring** - Check for new PRs every 15 minutes
- 🔍 **Semantic Search** - Find the 10 most similar Redmine issues for each PR
- 📄 **JSON Output** - Results saved to `pr_issue_links.json`
- 🎯 **Smart Tracking** - Avoids processing the same PR twice
- 🚀 **GitHub API** - Uses official GitHub REST API

## Quick Start

### 1. Run Once (Check Recent PRs)

```bash
cd watsonx-ceph-l3-north-america
python3 monitor_prs.py
```

This checks for PRs from the last 15 minutes.

### 2. Run Continuously (Monitor Every 15 Minutes)

```bash
python3 monitor_prs.py continuous 15
```

This will:
- Check for new PRs every 15 minutes
- Find 10 similar Redmine issues for each PR
- Save results to `pr_issue_links.json`
- Run until you press Ctrl+C

## Usage

### Commands

```bash
# Check last 15 minutes (default)
python3 monitor_prs.py

# Check last 60 minutes
python3 monitor_prs.py once 60

# Monitor continuously every 15 minutes
python3 monitor_prs.py continuous 15

# Monitor continuously every 30 minutes
python3 monitor_prs.py continuous 30

# Show all PR-issue links
python3 monitor_prs.py show
```

## Output Format

Results are saved to `pr_issue_links.json`:

```json
[
  {
    "pr": {
      "pr_number": 12345,
      "title": "Fix OSD crash on startup",
      "state": "open",
      "author": "username",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "url": "https://github.com/ceph/ceph/pull/12345",
      "labels": ["bug", "osd"],
      "draft": false
    },
    "similar_issues": [
      {
        "issue_id": "78000",
        "similarity_score": 0.892,
        "document": "Subject: OSD crashes on startup...",
        "metadata": {
          "issue_id": "78000",
          "subject": "OSD crashes on startup with segmentation fault",
          "status": "Open",
          "priority": "High",
          "url": "https://tracker.ceph.com/issues/78000"
        }
      },
      {
        "issue_id": "77993",
        "similarity_score": 0.856,
        "document": "Subject: startup crash due to race...",
        "metadata": {
          "issue_id": "77993",
          "subject": "startup crash due to race between lifecycle and quota handler",
          "status": "Fix Under Review",
          "priority": "Normal",
          "url": "https://tracker.ceph.com/issues/77993"
        }
      }
    ],
    "processed_at": "2024-01-15T10:35:00.123456",
    "search_text": "Title: Fix OSD crash on startup\nDescription: This PR fixes..."
  }
]
```

## Configuration

### Optional: GitHub Token (Recommended)

Without a token, you're limited to 60 requests/hour. With a token, you get 5000 requests/hour.

1. Create a GitHub Personal Access Token:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: `public_repo` (read-only access to public repos)
   - Copy the token

2. Add to `.env`:
```bash
echo "GITHUB_TOKEN=your_token_here" >> .env
```

### Embedding Model

The monitor uses the same embedding model as your database:

```bash
# In .env
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
```

## How It Works

1. **Fetch Recent PRs** - Uses GitHub API to get PRs created in the last N minutes
2. **Format PR Content** - Combines PR title, description, and labels into searchable text
3. **Semantic Search** - Searches your 30K Redmine issues for similar content
4. **Rank Results** - Returns top 10 most similar issues with similarity scores
5. **Save Results** - Appends to `pr_issue_links.json`
6. **Track Processed** - Saves PR numbers to `seen_prs.json` to avoid duplicates

## Use Cases

### 1. Find Related Issues for New PRs

When a new PR is created, automatically find related Redmine issues that might:
- Be fixed by this PR
- Provide context for reviewers
- Show duplicate work
- Highlight potential conflicts

### 2. Link PRs to Issues

Use the similarity scores to:
- Suggest which issues a PR might close
- Find related discussions
- Identify test cases from similar issues

### 3. Review Assistance

Help reviewers by:
- Showing historical context
- Finding similar bugs that were fixed
- Identifying patterns in related issues

## Examples

### Example 1: Check Last Hour

```bash
python3 monitor_prs.py once 60
```

Output:
```
================================================================================
Ceph GitHub PR Monitor
================================================================================

📊 Loading issue database from: ./chroma_db
🤖 Using embedding model: BAAI/bge-large-en-v1.5
🔑 Using GitHub token (higher rate limits)

Loading pipeline...
✅ Pipeline loaded

🔍 Checking for PRs from the last 60 minutes...

✅ Found 2 new PRs with similar issues
📄 Results saved to: pr_issue_links.json

PR #12345: Fix OSD crash on startup
   URL: https://github.com/ceph/ceph/pull/12345
   Similar issues: 10
   1. Issue #78000 (similarity: 0.892)
      OSD crashes on startup with segmentation fault
   2. Issue #77993 (similarity: 0.856)
      startup crash due to race between lifecycle and quota handler
   3. Issue #77970 (similarity: 0.834)
      OSD fails to initialize on boot

PR #12346: Improve RGW performance
   URL: https://github.com/ceph/ceph/pull/12346
   Similar issues: 10
   1. Issue #78006 (similarity: 0.823)
      rgw: optional distributed rate limit backends
   2. Issue #77969 (similarity: 0.801)
      mds: adaptive Group Commit for safe-reply journal flush batching
```

### Example 2: Continuous Monitoring

```bash
python3 monitor_prs.py continuous 15
```

Output:
```
================================================================================
Ceph GitHub PR Monitor
================================================================================

🔄 Starting continuous monitoring (checking every 15 minutes)
   Press Ctrl+C to stop

[2024-01-15 10:00:00] Checking for new PRs...
[2024-01-15 10:00:05] Found and processed 1 new PR
[2024-01-15 10:00:05] Sleeping for 15 minutes...

[2024-01-15 10:15:00] Checking for new PRs...
[2024-01-15 10:15:03] No new PRs found
[2024-01-15 10:15:03] Sleeping for 15 minutes...

[2024-01-15 10:30:00] Checking for new PRs...
[2024-01-15 10:30:07] Found and processed 2 new PRs
[2024-01-15 10:30:07] Sleeping for 15 minutes...
```

### Example 3: View All Links

```bash
python3 monitor_prs.py show
```

Output:
```
📊 Total PR-issue links: 25

PR #12345: Fix OSD crash on startup
   Processed: 2024-01-15T10:00:00.123456
   Similar issues: 10

PR #12346: Improve RGW performance
   Processed: 2024-01-15T10:15:00.234567
   Similar issues: 10
```

## Running as a Background Service

### Using nohup (Simple)

```bash
nohup python3 monitor_prs.py continuous 15 > pr_monitor.log 2>&1 &
```

Check the log:
```bash
tail -f pr_monitor.log
```

Stop it:
```bash
ps aux | grep monitor_prs.py
kill <PID>
```

### Using systemd (Linux)

Create `/etc/systemd/system/ceph-pr-monitor.service`:

```ini
[Unit]
Description=Ceph PR Monitor
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/watsonx-ceph-l3-north-america
ExecStart=/usr/bin/python3 monitor_prs.py continuous 15
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ceph-pr-monitor
sudo systemctl start ceph-pr-monitor
sudo systemctl status ceph-pr-monitor
```

View logs:
```bash
sudo journalctl -u ceph-pr-monitor -f
```

### Using cron (Periodic)

Run every 15 minutes:

```bash
crontab -e
```

Add:
```
*/15 * * * * cd /path/to/watsonx-ceph-l3-north-america && python3 monitor_prs.py once 20 >> pr_monitor.log 2>&1
```

## Troubleshooting

### Rate Limiting

**Error:** `API rate limit exceeded`

**Solution:** Add a GitHub token to `.env`:
```bash
GITHUB_TOKEN=your_token_here
```

### No PRs Found

**Possible reasons:**
- No new PRs in the time window
- All PRs already processed (check `seen_prs.json`)
- GitHub API issues

**Solution:** Try a longer time window:
```bash
python3 monitor_prs.py once 120  # Check last 2 hours
```

### Slow Performance

**Cause:** Embedding generation for each PR

**Solution:** 
- Use a faster embedding model (all-MiniLM-L6-v2)
- Reduce check frequency
- The first search is slow (model loading), subsequent ones are fast

## Files Created

- `pr_issue_links.json` - All PR-issue links with similarity scores
- `seen_prs.json` - List of processed PR numbers (prevents duplicates)
- `pr_monitor.log` - Log file (if using nohup)

## Integration Ideas

### 1. Slack/Discord Notifications

Modify the script to send notifications when new PRs are found.

### 2. GitHub Comments

Automatically comment on PRs with links to similar issues.

### 3. Dashboard

Build a web dashboard to visualize PR-issue relationships.

### 4. CI/CD Integration

Run the monitor in your CI/CD pipeline to check PRs during review.

## Summary

You now have an automated system that:
- ✅ Monitors Ceph GitHub PRs every 15 minutes
- ✅ Finds 10 most similar Redmine issues for each PR
- ✅ Saves results to JSON for easy processing
- ✅ Tracks processed PRs to avoid duplicates
- ✅ Runs continuously in the background

Start monitoring:
```bash
python3 monitor_prs.py continuous 15