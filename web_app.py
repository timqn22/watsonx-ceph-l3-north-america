"""
Flask Web Application for Ceph Issue Semantic Search
Deploy this on PythonAnywhere to provide web-based search
"""

from flask import Flask, request, jsonify, render_template_string
import os
from src.pipeline import IssuePipeline

app = Flask(__name__)

# Initialize pipeline (loads the vector database)
pipeline = None

def get_pipeline():
    """Lazy load the pipeline to avoid loading on import"""
    global pipeline
    if pipeline is None:
        persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
        collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
        embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        
        pipeline = IssuePipeline(
            persist_directory=persist_dir,
            collection_name=collection_name,
            embedding_model=embedding_model
        )
    return pipeline

# HTML template for the search interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ceph Issue Search</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .search-box {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .search-form {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .search-input {
            flex: 1;
            padding: 15px 20px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            outline: none;
            transition: border-color 0.3s;
        }
        
        .search-input:focus {
            border-color: #667eea;
        }
        
        .search-button {
            padding: 15px 40px;
            font-size: 16px;
            font-weight: 600;
            color: white;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .search-button:hover {
            transform: translateY(-2px);
        }
        
        .search-button:active {
            transform: translateY(0);
        }
        
        .filters {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .filter-group label {
            font-weight: 500;
            color: #666;
        }
        
        .filter-select {
            padding: 8px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            outline: none;
            cursor: pointer;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            display: none;
        }
        
        .loading.active {
            display: block;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .results {
            display: none;
        }
        
        .results.active {
            display: block;
        }
        
        .result-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .result-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.12);
        }
        
        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
        }
        
        .result-title {
            flex: 1;
        }
        
        .result-title h3 {
            color: #333;
            font-size: 1.3em;
            margin-bottom: 8px;
        }
        
        .result-title a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        
        .result-title a:hover {
            text-decoration: underline;
        }
        
        .similarity-badge {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
        }
        
        .result-meta {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        
        .meta-item {
            display: flex;
            align-items: center;
            gap: 5px;
            color: #666;
            font-size: 0.9em;
        }
        
        .badge {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .badge-status {
            background: #e3f2fd;
            color: #1976d2;
        }
        
        .badge-priority {
            background: #fff3e0;
            color: #f57c00;
        }
        
        .result-preview {
            color: #666;
            line-height: 1.6;
            margin-top: 10px;
        }
        
        .no-results {
            text-align: center;
            padding: 60px 20px;
            background: white;
            border-radius: 12px;
            display: none;
        }
        
        .no-results.active {
            display: block;
        }
        
        .no-results h3 {
            color: #666;
            font-size: 1.5em;
            margin-bottom: 10px;
        }
        
        .stats {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Ceph Issue Search</h1>
            <p>Semantic search across {{ stats.total_issues }} Ceph issues</p>
        </div>
        
        <div class="stats">
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{{ stats.total_issues }}</div>
                    <div class="stat-label">Total Issues</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ stats.embedding_dimension }}</div>
                    <div class="stat-label">Embedding Dimensions</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ stats.embedding_model.split('/')[-1] }}</div>
                    <div class="stat-label">Model</div>
                </div>
            </div>
        </div>
        
        <div class="search-box">
            <form class="search-form" onsubmit="performSearch(event)">
                <input 
                    type="text" 
                    class="search-input" 
                    id="searchQuery"
                    placeholder="Search for issues... (e.g., 'OSD crashes on startup')"
                    required
                >
                <button type="submit" class="search-button">Search</button>
            </form>
            
            <div class="filters">
                <div class="filter-group">
                    <label for="limitSelect">Results:</label>
                    <select id="limitSelect" class="filter-select">
                        <option value="5">5</option>
                        <option value="10" selected>10</option>
                        <option value="20">20</option>
                        <option value="50">50</option>
                    </select>
                </div>
            </div>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Searching through issues...</p>
        </div>
        
        <div class="no-results" id="noResults">
            <h3>No results found</h3>
            <p>Try a different search query</p>
        </div>
        
        <div class="results" id="results"></div>
    </div>
    
    <script>
        async function performSearch(event) {
            event.preventDefault();
            
            const query = document.getElementById('searchQuery').value;
            const limit = document.getElementById('limitSelect').value;
            
            // Show loading, hide results
            document.getElementById('loading').classList.add('active');
            document.getElementById('results').classList.remove('active');
            document.getElementById('noResults').classList.remove('active');
            
            try {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: query,
                        limit: parseInt(limit)
                    })
                });
                
                const data = await response.json();
                
                // Hide loading
                document.getElementById('loading').classList.remove('active');
                
                if (data.results && data.results.length > 0) {
                    displayResults(data.results);
                } else {
                    document.getElementById('noResults').classList.add('active');
                }
            } catch (error) {
                console.error('Search error:', error);
                document.getElementById('loading').classList.remove('active');
                alert('Search failed. Please try again.');
            }
        }
        
        function displayResults(results) {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '';
            
            results.forEach((result, index) => {
                const card = document.createElement('div');
                card.className = 'result-card';
                
                const similarity = (result.similarity_score * 100).toFixed(1);
                const metadata = result.metadata;
                
                card.innerHTML = `
                    <div class="result-header">
                        <div class="result-title">
                            <h3>
                                <a href="${metadata.url}" target="_blank">
                                    #${metadata.issue_id}: ${metadata.subject}
                                </a>
                            </h3>
                        </div>
                        <div class="similarity-badge">${similarity}% match</div>
                    </div>
                    
                    <div class="result-meta">
                        <div class="meta-item">
                            <span class="badge badge-status">${metadata.status}</span>
                        </div>
                        <div class="meta-item">
                            <span class="badge badge-priority">${metadata.priority}</span>
                        </div>
                        ${metadata.category ? `
                        <div class="meta-item">
                            📁 ${metadata.category}
                        </div>
                        ` : ''}
                        <div class="meta-item">
                            👤 ${metadata.author}
                        </div>
                        <div class="meta-item">
                            📅 ${new Date(metadata.created_on).toLocaleDateString()}
                        </div>
                    </div>
                    
                    <div class="result-preview">
                        ${result.document.substring(0, 300)}...
                    </div>
                `;
                
                resultsDiv.appendChild(card);
            });
            
            resultsDiv.classList.add('active');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the search interface"""
    pipeline = get_pipeline()
    stats = pipeline.get_stats()
    return render_template_string(HTML_TEMPLATE, stats=stats['vector_store'])

@app.route('/api/search', methods=['POST'])
def search():
    """API endpoint for searching issues"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        limit = data.get('limit', 10)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Perform search
        pipeline = get_pipeline()
        results = pipeline.search_similar_issues(
            query=query,
            n_results=limit
        )
        
        return jsonify({
            'query': query,
            'results': results,
            'count': len(results)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/similar/<issue_id>')
def similar(issue_id):
    """API endpoint for finding similar issues"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        pipeline = get_pipeline()
        results = pipeline.find_similar_to_issue(
            issue_id=issue_id,
            n_results=limit
        )
        
        return jsonify({
            'issue_id': issue_id,
            'results': results,
            'count': len(results)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def stats():
    """API endpoint for database statistics"""
    try:
        pipeline = get_pipeline()
        stats = pipeline.get_stats()
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000)

# Made with Bob
