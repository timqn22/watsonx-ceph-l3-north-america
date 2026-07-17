#!/usr/bin/env python3
"""
Web viewer for GitHub PR monitoring results
Simple Flask app to view PR-issue links in a browser 
"""

import json
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# HTML template for viewing results
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub PR Monitor - Results</title>
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
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #333;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #666;
            font-size: 14px;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .stat-card h3 {
            color: #667eea;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }
        
        .controls {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .search-box {
            flex: 1;
            min-width: 300px;
            display: flex;
            gap: 10px;
        }
        
        .search-input {
            flex: 1;
            padding: 10px 15px;
            border: 2px solid #e0e7ff;
            border-radius: 5px;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        .search-input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .search-input::placeholder {
            color: #999;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5568d3;
        }
        
        .btn-secondary {
            background: #e0e7ff;
            color: #667eea;
        }
        
        .btn-secondary:hover {
            background: #c7d2fe;
        }
        
        .pr-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .pr-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .pr-title {
            flex: 1;
        }
        
        .pr-title h2 {
            color: #333;
            font-size: 20px;
            margin-bottom: 5px;
        }
        
        .pr-title a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        
        .pr-title a:hover {
            text-decoration: underline;
        }
        
        .pr-meta {
            display: flex;
            gap: 15px;
            font-size: 13px;
            color: #666;
            margin-top: 8px;
        }
        
        .pr-meta span {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .badge-open {
            background: #dcfce7;
            color: #166534;
        }
        
        .badge-closed {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .badge-draft {
            background: #f3f4f6;
            color: #4b5563;
        }
        
        .similar-issues {
            margin-top: 20px;
        }
        
        .similar-issues h3 {
            color: #333;
            font-size: 16px;
            margin-bottom: 15px;
        }
        
        .issue-item {
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }
        
        .issue-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 8px;
        }
        
        .issue-title {
            flex: 1;
            font-weight: 500;
            color: #333;
        }
        
        .issue-title a {
            color: #333;
            text-decoration: none;
        }
        
        .issue-title a:hover {
            color: #667eea;
        }
        
        .similarity-score {
            background: #667eea;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }
        
        .issue-meta {
            font-size: 12px;
            color: #666;
            display: flex;
            gap: 15px;
        }
        
        .no-results {
            background: white;
            padding: 60px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .no-results h2 {
            color: #333;
            margin-bottom: 10px;
        }
        
        .no-results p {
            color: #666;
            margin-bottom: 20px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 18px;
        }
        
        .error {
            background: #fee2e2;
            color: #991b1b;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .filter-info {
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 GitHub PR Monitor</h1>
            <p>Automatically linking GitHub PRs to similar Redmine issues</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Total PRs</h3>
                <div class="value" id="total-prs">{{ total_prs }}</div>
            </div>
            <div class="stat-card">
                <h3>Total Links</h3>
                <div class="value" id="total-links">{{ total_links }}</div>
            </div>
            <div class="stat-card">
                <h3>Last Updated</h3>
                <div class="value" style="font-size: 16px;" id="last-updated">{{ last_updated }}</div>
            </div>
        </div>
        
        <div class="controls">
            <div class="search-box">
                <input type="text"
                       class="search-input"
                       id="search-input"
                       placeholder="Search by PR number or title (e.g., 12345 or 'fix bug')..."
                       onkeyup="searchPRs()">
                <button class="btn btn-secondary" onclick="clearSearch()">Clear</button>
            </div>
            <button class="btn btn-primary" onclick="refreshData()">🔄 Refresh</button>
            <button class="btn btn-secondary" onclick="filterByState('all')">All PRs</button>
            <button class="btn btn-secondary" onclick="filterByState('open')">Open Only</button>
            <button class="btn btn-secondary" onclick="filterByState('closed')">Closed Only</button>
            <span class="filter-info" id="filter-info">Showing all PRs</span>
        </div>
        
        <div id="results-container">
            {% if results %}
                {% for result in results %}
                <div class="pr-card"
                     data-state="{{ result.pr.state }}"
                     data-pr-number="{{ result.pr.pr_number }}"
                     data-pr-title="{{ result.pr.title }}">
                    <div class="pr-header">
                        <div class="pr-title">
                            <h2>
                                <a href="{{ result.pr.url }}" target="_blank">
                                    PR #{{ result.pr.pr_number }}: {{ result.pr.title }}
                                </a>
                            </h2>
                            <div class="pr-meta">
                                <span>
                                    {% if result.pr.state == 'open' %}
                                        <span class="badge badge-open">Open</span>
                                    {% else %}
                                        <span class="badge badge-closed">Closed</span>
                                    {% endif %}
                                    {% if result.pr.draft %}
                                        <span class="badge badge-draft">Draft</span>
                                    {% endif %}
                                </span>
                                <span>👤 {{ result.pr.author }}</span>
                                <span>📅 {{ result.pr.created_at[:10] }}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="similar-issues">
                        <h3>🔍 Similar Redmine Issues ({{ result.similar_issues|length }})</h3>
                        {% for issue in result.similar_issues %}
                        <div class="issue-item">
                            <div class="issue-header">
                                <div class="issue-title">
                                    <a href="{{ issue.metadata.url }}" target="_blank">
                                        #{{ issue.issue_id }}: {{ issue.metadata.subject }}
                                    </a>
                                </div>
                                <span class="similarity-score">
                                    {{ "%.1f"|format(issue.similarity_score * 100) }}%
                                </span>
                            </div>
                            <div class="issue-meta">
                                <span>Status: {{ issue.metadata.status }}</span>
                                {% if issue.metadata.priority %}
                                <span>Priority: {{ issue.metadata.priority }}</span>
                                {% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-results">
                    <h2>No Results Yet</h2>
                    <p>The PR monitor hasn't found any PRs yet. Make sure the monitoring service is running.</p>
                    <button class="btn btn-primary" onclick="refreshData()">🔄 Refresh</button>
                </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        let currentFilter = 'all';
        let currentSearch = '';
        
        function refreshData() {
            location.reload();
        }
        
        function searchPRs() {
            const searchInput = document.getElementById('search-input');
            currentSearch = searchInput.value.toLowerCase().trim();
            applyFilters();
        }
        
        function clearSearch() {
            document.getElementById('search-input').value = '';
            currentSearch = '';
            applyFilters();
        }
        
        function filterByState(state) {
            currentFilter = state;
            applyFilters();
        }
        
        function applyFilters() {
            const cards = document.querySelectorAll('.pr-card');
            const filterInfo = document.getElementById('filter-info');
            
            let visibleCount = 0;
            cards.forEach(card => {
                let showCard = true;
                
                // Apply state filter
                if (currentFilter !== 'all' && card.dataset.state !== currentFilter) {
                    showCard = false;
                }
                
                // Apply search filter
                if (currentSearch && showCard) {
                    const prNumber = card.dataset.prNumber || '';
                    const prTitle = card.dataset.prTitle || '';
                    
                    const matchesNumber = prNumber.includes(currentSearch);
                    const matchesTitle = prTitle.toLowerCase().includes(currentSearch);
                    
                    if (!matchesNumber && !matchesTitle) {
                        showCard = false;
                    }
                }
                
                if (showCard) {
                    card.style.display = 'block';
                    visibleCount++;
                } else {
                    card.style.display = 'none';
                }
            });
            
            // Update filter info
            let filterText = '';
            if (currentSearch) {
                filterText = `Search: "${currentSearch}" - `;
            }
            if (currentFilter === 'all') {
                filterText += `Showing ${visibleCount} PRs`;
            } else {
                filterText += `Showing ${visibleCount} ${currentFilter} PRs`;
            }
            filterInfo.textContent = filterText;
        }
        
        // Auto-refresh every 60 seconds
        setInterval(refreshData, 60000);
    </script>
</body>
</html>
"""


def load_results():
    """Load PR-issue links from JSON file"""
    results_file = Path('pr_issue_links.json')
    if results_file.exists():
        try:
            with open(results_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading results: {e}")
            return []
    return []


@app.route('/')
def index():
    """Main page showing all PR-issue links"""
    results = load_results()
    
    # Calculate stats
    total_prs = len(results)
    total_links = sum(len(r.get('similar_issues', [])) for r in results)
    
    # Get last updated time
    last_updated = "Never"
    if results:
        try:
            last_result = results[-1]
            if 'processed_at' in last_result:
                dt = datetime.fromisoformat(last_result['processed_at'].replace('Z', '+00:00'))
                last_updated = dt.strftime('%Y-%m-%d %H:%M')
        except:
            pass
    
    return render_template_string(
        HTML_TEMPLATE,
        results=results,
        total_prs=total_prs,
        total_links=total_links,
        last_updated=last_updated
    )


@app.route('/api/results')
def api_results():
    """API endpoint to get results as JSON"""
    results = load_results()
    return jsonify({
        'success': True,
        'count': len(results),
        'results': results
    })


@app.route('/api/stats')
def api_stats():
    """API endpoint to get statistics"""
    results = load_results()
    
    total_prs = len(results)
    total_links = sum(len(r.get('similar_issues', [])) for r in results)
    
    # Count by state
    open_prs = sum(1 for r in results if r.get('pr', {}).get('state') == 'open')
    closed_prs = total_prs - open_prs
    
    return jsonify({
        'success': True,
        'stats': {
            'total_prs': total_prs,
            'total_links': total_links,
            'open_prs': open_prs,
            'closed_prs': closed_prs,
            'avg_links_per_pr': round(total_links / total_prs, 2) if total_prs > 0 else 0
        }
    })


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PR Results Viewer')
    parser.add_argument('--port', type=int, default=5001,
                       help='Port to run server on (default: 5001)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind to (default: 0.0.0.0)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"🌐 PR Results Viewer Starting")
    print(f"{'='*60}")
    print(f"Server: http://localhost:{args.port}")
    print(f"\nOpen this URL in your browser to view PR-issue links")
    print(f"{'='*60}\n")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()

# Made with Bob
