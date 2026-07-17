# Getting Started - Complete Guide

This guide will walk you through running the GitHub PR monitoring system step-by-step.

## 📋 Prerequisites

Make sure you have:
- Python 3.8 or higher installed
- Git installed
- Terminal/command line access

## 🚀 Step-by-Step Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/timqn22/watsonx-ceph-l3-north-america.git
cd watsonx-ceph-l3-north-america
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install all required packages including Flask, ChromaDB, sentence-transformers, etc.

### Step 3: Verify Installation

```bash
python3 --version  # Should be 3.8 or higher
pip list | grep flask  # Should show flask is installed
```

## 🎯 Running the PR Monitor

You have two options: **Server Mode** (recommended) or **CLI Mode**.

---

## Option 1: Server Mode (Recommended) 🌐

This runs continuously in the background and provides a web interface.

### Step 1: Start the PR Monitor Server

Open a terminal and run:

```bash
cd watsonx-ceph-l3-north-america
python3 pr_monitor_server.py --autostart
```

**What happens on first run:**
- Processes only the **10 most recent PRs** (not all historical PRs)
- After that, checks for **new PRs only** every 15 minutes
- You can change the initial count: `--initial-prs 20`

You should see:
```
🚀 PR Monitor Server Starting
Server: http://0.0.0.0:8001
Status: http://localhost:8001/status
First run will process 10 most recent PRs
...
```

**Keep this terminal open!** The server is now running.

### Step 2: Start the Web Viewer

Open a **NEW terminal** (keep the first one running) and run:

```bash
cd watsonx-ceph-l3-north-america
python3 pr_results_viewer.py
```

You should see:
```
🌐 PR Results Viewer Starting
Server: http://localhost:5001
Open this URL in your browser to view PR-issue links
```

### Step 3: View Results in Browser

Open your web browser and go to:

**http://localhost:5001**

You'll see a beautiful web interface showing:
- Total PRs monitored
- Total issue links found
- List of all PRs with their similar Redmine issues
- Similarity scores for each match

### Step 4: Check Status

In a third terminal, you can check the monitoring status:

```bash
curl http://localhost:8001/status
```

Or open in browser: **http://localhost:8001/status**

---

## Option 2: CLI Mode (Simple) 💻

This runs one-time checks manually.

### Run a Single Check

```bash
cd watsonx-ceph-l3-north-america
python3 monitor_prs.py
```

This will:
1. Check for PRs created in the last 15 minutes
2. Find similar Redmine issues
3. Save results to `pr_issue_links.json`

### View Results

```bash
# View the JSON file
cat pr_issue_links.json | python3 -m json.tool

# Or use the web viewer
python3 pr_results_viewer.py
# Then open http://localhost:5001
```

---

## 📊 Understanding the Output

### Web Interface (http://localhost:5001)

The web interface shows:

1. **Statistics Cards**
   - Total PRs: Number of PRs monitored
   - Total Links: Number of similar issues found
   - Last Updated: When the last check ran

2. **PR Cards**
   - PR number and title (clickable link to GitHub)
   - Author and creation date
   - State (Open/Closed/Draft)
   - List of similar Redmine issues with similarity scores

3. **Filters**
   - All PRs
   - Open Only
   - Closed Only

### JSON File (pr_issue_links.json)

```json
[
  {
    "pr": {
      "pr_number": 12345,
      "title": "Fix OSD crash on startup",
      "url": "https://github.com/ceph/ceph/pull/12345",
      "author": "username",
      "created_at": "2024-01-15T10:30:00Z",
      "state": "open"
    },
    "similar_issues": [
      {
        "issue_id": "78000",
        "similarity_score": 0.892,
        "metadata": {
          "subject": "OSD crashes on startup",
          "status": "Open",
          "priority": "High",
          "url": "https://tracker.ceph.com/issues/78000"
        }
      }
    ]
  }
]
```

---

## 🔧 Configuration

### Optional: Add GitHub Token

For higher rate limits (5000/hour instead of 60/hour):

```bash
# Create .env file
echo "GITHUB_TOKEN=your_github_token_here" >> .env
```

Get a token at: https://github.com/settings/tokens
- Required permission: `public_repo` (read-only)

### Change Check Interval

```bash
# Check every 30 minutes instead of 15
python3 pr_monitor_server.py --autostart --interval 30
```

### Change Port

```bash
# Run monitor server on different port
python3 pr_monitor_server.py --autostart --port 8002

# Run web viewer on different port
python3 pr_results_viewer.py --port 5002
```

---

## 🎮 Common Commands

### Check if Server is Running

```bash
curl http://localhost:8001/health
```

### Get Current Status

```bash
curl http://localhost:8001/status | python3 -m json.tool
```

### Trigger Manual Check

```bash
curl -X POST http://localhost:8001/check-now
```

### Stop Monitoring

```bash
curl -X POST http://localhost:8001/stop
```

### Start Monitoring

```bash
curl -X POST http://localhost:8001/start
```

### View Results via API

```bash
curl http://localhost:8001/results | python3 -m json.tool
```

---

## 🐛 Troubleshooting

### "Port already in use"

If you see an error about port 8001 or 5001 being in use:

```bash
# Use different ports
python3 pr_monitor_server.py --autostart --port 8002
python3 pr_results_viewer.py --port 5002
```

### "No module named 'flask'"

Install dependencies:

```bash
pip install -r requirements.txt
```

### "No results yet"

The monitor needs time to find PRs. Wait 15 minutes or trigger a manual check:

```bash
curl -X POST http://localhost:8001/check-now
```

### Can't Access from Browser

Make sure:
1. The server is running (check terminal)
2. You're using the correct URL: http://localhost:5001
3. Try http://127.0.0.1:5001 instead

### Server Stopped Working

Check the logs:

```bash
tail -f pr_monitor.log
```

Restart the server:

```bash
# Stop (Ctrl+C in the terminal)
# Then start again
python3 pr_monitor_server.py --autostart
```

---

## 📱 Quick Reference

### URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Web Viewer | http://localhost:5001 | View PR-issue links in browser |
| Monitor Status | http://localhost:8001/status | Check monitoring status |
| Monitor Health | http://localhost:8001/health | Health check |
| API Results | http://localhost:8001/results | Get results as JSON |

### Files

| File | Purpose |
|------|---------|
| `pr_issue_links.json` | All PR-issue mappings |
| `seen_prs.json` | Tracked PR numbers |
| `pr_monitor.log` | Server logs |

### Commands

| Command | Purpose |
|---------|---------|
| `python3 pr_monitor_server.py --autostart` | Start monitoring server |
| `python3 pr_results_viewer.py` | Start web viewer |
| `python3 monitor_prs.py` | Run one-time check |
| `curl http://localhost:8001/status` | Check status |
| `curl -X POST http://localhost:8001/check-now` | Trigger check |

---

## 🎓 Next Steps

1. **Let it run**: The monitor will check for new PRs every 15 minutes
2. **Check the web interface**: Refresh http://localhost:5001 to see new results
3. **Integrate**: Use the API endpoints to integrate with other tools
4. **Customize**: Adjust check intervals, filters, etc.

## 📚 More Documentation

- [PR_SERVER_GUIDE.md](PR_SERVER_GUIDE.md) - Detailed server documentation
- [PR_MONITORING_GUIDE.md](PR_MONITORING_GUIDE.md) - CLI monitoring guide
- [API_SERVER_GUIDE.md](API_SERVER_GUIDE.md) - API documentation
- [README.md](README.md) - Full project documentation

---

## 💡 Tips

1. **Run in Background**: Use `screen` or `tmux` to keep servers running
2. **Auto-start on Boot**: Set up systemd service (see PR_SERVER_GUIDE.md)
3. **Monitor Logs**: Keep an eye on `pr_monitor.log` for issues
4. **GitHub Token**: Add one to avoid rate limits
5. **Refresh Browser**: The web interface auto-refreshes every 60 seconds

---

## ✅ Success Checklist

- [ ] Cloned repository
- [ ] Installed dependencies
- [ ] Started PR monitor server
- [ ] Started web viewer
- [ ] Opened http://localhost:5001 in browser
- [ ] Saw PR results (or waiting for first check)
- [ ] Checked status at http://localhost:8001/status

If all boxes are checked, you're all set! 🎉