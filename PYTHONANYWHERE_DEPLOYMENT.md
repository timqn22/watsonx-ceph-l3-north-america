# Deploying to PythonAnywhere

This guide will help you deploy the Ceph Issue Search web application to PythonAnywhere.

## Prerequisites

1. **PythonAnywhere Account** - Sign up at https://www.pythonanywhere.com (free tier works)
2. **Your ChromaDB Database** - The `chroma_db/` folder with your 30K scraped issues
3. **Embedding Model** - The sentence-transformers model you used

## Step 1: Upload Your Files

### Option A: Using Git (Recommended)

1. Push your code to GitHub:
```bash
cd watsonx-ceph-l3-north-america
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

2. On PythonAnywhere, open a Bash console and clone:
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### Option B: Upload Directly

1. Go to PythonAnywhere → Files
2. Upload your project files
3. Upload the `chroma_db/` folder (this may take a while - 30K issues = ~20-35 GB)

**Note:** For large databases, consider:
- Using rsync over SSH (if you have a paid account)
- Scraping directly on PythonAnywhere
- Using a smaller subset initially

## Step 2: Set Up Virtual Environment

In a PythonAnywhere Bash console:

```bash
cd ~/watsonx-ceph-l3-north-america

# Create virtual environment
python3.10 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Important:** This will download the embedding model (~80MB for MiniLM or ~1.3GB for BGE-large). This happens automatically on first run.

## Step 3: Configure Environment Variables

Create a `.env` file:

```bash
cd ~/watsonx-ceph-l3-north-america
nano .env
```

Add:
```bash
CHROMA_PERSIST_DIR=./chroma_db
COLLECTION_NAME=ceph_issues
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

Save and exit (Ctrl+X, Y, Enter)

## Step 4: Configure Web App

1. Go to PythonAnywhere → Web
2. Click "Add a new web app"
3. Choose "Manual configuration"
4. Select Python 3.10

### Configure WSGI File

Click on the WSGI configuration file link and replace its contents with:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/YOUR_USERNAME/watsonx-ceph-l3-north-america'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['CHROMA_PERSIST_DIR'] = os.path.join(project_home, 'chroma_db')
os.environ['COLLECTION_NAME'] = 'ceph_issues'
os.environ['EMBEDDING_MODEL'] = 'all-MiniLM-L6-v2'

# Import Flask app
from web_app import app as application
```

**Replace `YOUR_USERNAME` with your actual PythonAnywhere username!**

### Configure Virtual Environment

In the Web tab:
1. Find "Virtualenv" section
2. Enter: `/home/YOUR_USERNAME/watsonx-ceph-l3-north-america/venv`

### Configure Static Files (Optional)

If you want to serve static files:
- URL: `/static/`
- Directory: `/home/YOUR_USERNAME/watsonx-ceph-l3-north-america/static/`

## Step 5: Reload and Test

1. Click the green "Reload" button
2. Visit your app at: `https://YOUR_USERNAME.pythonanywhere.com`

## Step 6: Test the Application

Your web app should now be live! Test it:

1. **Home Page:** `https://YOUR_USERNAME.pythonanywhere.com`
2. **Search:** Enter a query like "OSD crashes on startup"
3. **API:** `https://YOUR_USERNAME.pythonanywhere.com/api/stats`

## Troubleshooting

### Error: "No module named 'flask'"

```bash
source ~/watsonx-ceph-l3-north-america/venv/bin/activate
pip install flask
```

### Error: "ChromaDB not found"

Check that `chroma_db/` folder is uploaded and path is correct in WSGI file.

### Error: "Model download failed"

The embedding model downloads on first run. Check:
```bash
cd ~/watsonx-ceph-l3-north-america
source venv/bin/activate
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Error: "Out of memory"

Free tier has limited RAM. Solutions:
1. Use smaller embedding model (`all-MiniLM-L6-v2` instead of `BAAI/bge-large-en-v1.5`)
2. Reduce database size
3. Upgrade to paid tier

### Slow First Load

First request loads the model into memory (~30 seconds). Subsequent requests are fast.

## Performance Optimization

### 1. Keep App Warm

Free tier apps sleep after inactivity. Keep it warm:
- Use a service like UptimeRobot to ping every 5 minutes
- Upgrade to paid tier for always-on

### 2. Reduce Database Size

If 30K issues is too large:
```bash
# On your local machine, scrape fewer issues
python3 cli.py reset
python3 cli.py scrape --max-issues 5000

# Then upload the smaller chroma_db/
```

### 3. Use Smaller Model

In `.env`:
```bash
EMBEDDING_MODEL=all-MiniLM-L6-v2  # 80MB, fast
# Instead of:
# EMBEDDING_MODEL=BAAI/bge-large-en-v1.5  # 1.3GB, slower
```

## API Endpoints

Your deployed app provides these endpoints:

### Web Interface
- `GET /` - Search interface

### API Endpoints
- `POST /api/search` - Search issues
  ```bash
  curl -X POST https://YOUR_USERNAME.pythonanywhere.com/api/search \
    -H "Content-Type: application/json" \
    -d '{"query": "OSD crash", "limit": 10}'
  ```

- `GET /api/similar/<issue_id>` - Find similar issues
  ```bash
  curl https://YOUR_USERNAME.pythonanywhere.com/api/similar/78000?limit=10
  ```

- `GET /api/stats` - Database statistics
  ```bash
  curl https://YOUR_USERNAME.pythonanywhere.com/api/stats
  ```

- `GET /health` - Health check
  ```bash
  curl https://YOUR_USERNAME.pythonanywhere.com/health
  ```

## Updating Your App

To update after making changes:

```bash
# SSH into PythonAnywhere
cd ~/watsonx-ceph-l3-north-america
git pull  # If using Git
source venv/bin/activate
pip install -r requirements.txt  # If dependencies changed

# Reload the web app from the Web tab
```

## Cost Considerations

### Free Tier Limitations:
- 512 MB disk space (may not fit 30K issues + model)
- Limited CPU/RAM
- App sleeps after inactivity
- One web app only

### Paid Tier Benefits ($5/month):
- More disk space (3GB+)
- Better performance
- Always-on apps
- Multiple web apps
- SSH access

## Alternative: Scrape on PythonAnywhere

Instead of uploading, scrape directly on PythonAnywhere:

```bash
cd ~/watsonx-ceph-l3-north-america
source venv/bin/activate

# Scrape issues (this will take time)
python3 cli.py scrape --max-issues 5000

# Then reload your web app
```

This avoids uploading large files but takes time to scrape.

## Security Notes

1. **No Authentication** - The app is public. Anyone can search.
2. **Rate Limiting** - Consider adding rate limiting for production
3. **API Keys** - Don't commit `.env` with sensitive data

## Example Usage

Once deployed, users can:

1. **Visit your URL:** `https://YOUR_USERNAME.pythonanywhere.com`
2. **Search:** Type "memory leak in monitor" and click Search
3. **View Results:** See top 10 most relevant issues with similarity scores
4. **Click Links:** Go directly to Ceph tracker for full details

## Support

- PythonAnywhere Help: https://help.pythonanywhere.com
- PythonAnywhere Forums: https://www.pythonanywhere.com/forums/
- This Project Issues: [Your GitHub Issues]

## Summary

Your Ceph Issue Search is now live at:
```
https://YOUR_USERNAME.pythonanywhere.com
```

Users can search 30,000 Ceph issues with semantic search and get instant results!