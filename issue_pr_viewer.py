#!/usr/bin/env python3
"""
Issue-to-PR Viewer
Shows Redmine issues and their similar GitHub PRs (similarity > 0.85)
"""

import json
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# HTML template for viewing issue→PR results
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Issue-PR Viewer - Redmine Issues → GitHub PRs</title>
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
            color: #764ba2;
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
            border-color: #764ba2;
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
            background: #764ba2;
            color: white;
        }
        
        .btn-primary:hover {
            background: #6a3f92;
        }
        
        .btn-secondary {
            background: #e0e7ff;
            color: #764ba2;
        }
        
        .btn-secondary:hover {
            background: #c7d2fe;
        }
        
        .filter-info {
            color: #666;
            font-size: 14px;
        }
        
        .issue-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .issue-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .issue-title {
            flex: 1;
        }
        
        .issue-title h2 {
            color: #333;
            font-size: 20px;
            margin-bottom: 5px;
        }
        
        .issue-title a {
            color: #764ba2;
            text-decoration: none;
            font-weight: 500;
        }
        
        .issue-title a:hover {
            text-decoration: underline;
        }
        
        .issue-meta {
            display: flex;
            gap: 15px;
            font-size: 13px;
            color: #666;
            margin-top: 8px;
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
        
        .badge-high {
            background: #fef3c7;
            color: #92400e;
        }
        
        .similar-prs {
            margin-top: 20px;
        }
        
        .similar-prs h3 {
            color: #333;
            font-size: 16px;
            margin-bottom: 15px;
        }
        
        .pr-item {
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #764ba2;
        }
        
        .pr-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 8px;
        }
        
        .pr-title {
            flex: 1;
            font-weight: 500;
            color: #333;
        }
        
        .pr-title a {
            color: #333;
            text-decoration: none;
        }
        
        .pr-title a:hover {
            color: #764ba2;
        }
        
        .similarity-score {
            background: #764ba2;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }
        
        .pr-meta {
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
        
        .pagination {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-top: 30px;
            text-align: center;
        }
        
        .pagination-info {
            color: #666;
            margin-bottom: 15px;
        }
        
        .pagination-buttons {
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 Issue-PR Viewer</h1>
            <p>Redmine Issues → Similar GitHub PRs (Similarity > 85%)</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Total Issues</h3>
                <div class="value">{{ total_issues }}</div>
            </div>
            <div class="stat-card">
                <h3>Total PR Links</h3>
                <div class="value">{{ total_links }}</div>
            </div>
            <div class="stat-card">
                <h3>Showing</h3>
                <div class="value" style="font-size: 16px;">{{ showing_count }} issues</div>
            </div>
        </div>
        
        <div class="controls">
            <div class="search-box">
                <input type="text" 
                       class="search-input" 
                       id="search-input" 
                       placeholder="Search by issue number or subject..."
                       onkeyup="searchIssues()">
                <button class="btn btn-secondary" onclick="clearSearch()">Clear</button>
            </div>
            <button class="btn btn-primary" onclick="refreshData()">🔄 Refresh</button>
            <span class="filter-info" id="filter-info">Showing {{ showing_count }} issues</span>
        </div>
        
        <div id="results-container">
            {% if results %}
                {% for result in results %}
                <div class="issue-card" 
                     data-issue-id="{{ result.issue.issue_id }}"
                     data-issue-subject="{{ result.issue.subject }}">
                    <div class="issue-header">
                        <div class="issue-title">
                            <h2>
                                <a href="{{ result.issue.url }}" target="_blank">
                                    Issue #{{ result.issue.issue_id }}: {{ result.issue.subject }}
                                </a>
                            </h2>
                            <div class="issue-meta">
                                <span>
                                    {% if result.issue.status == 'Open' or result.issue.status == 'New' %}
                                        <span class="badge badge-open">{{ result.issue.status }}</span>
                                    {% else %}
                                        <span class="badge badge-closed">{{ result.issue.status }}</span>
                                    {% endif %}
                                    {% if result.issue.priority %}
                                        <span class="badge badge-high">{{ result.issue.priority }}</span>
                                    {% endif %}
                                </span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="similar-prs">
                        <h3>🔍 Similar GitHub PRs ({{ result.similar_prs|length }})</h3>
                        {% for pr in result.similar_prs %}
                        <div class="pr-item">
                            <div class="pr-header">
                                <div class="pr-title">
                                    <a href="{{ pr.metadata.url }}" target="_blank">
                                        PR #{{ pr.pr_number }}: {{ pr.metadata.title }}
                                    </a>
                                </div>
                                <span class="similarity-score">
                                    {{ "%.1f"|format(pr.similarity_score * 100) }}%
                                </span>
                            </div>
                            <div class="pr-meta">
                                <span>State: {{ pr.metadata.state }}</span>
                                <span>Author: {{ pr.metadata.author }}</span>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-results">
                    <h2>No Results Yet</h2>
                    <p>Run the issue-PR link generator first:</p>
                    <code>python3 generate_issue_pr_links.py --issues 50</code>
                </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        let currentSearch = '';
        
        function refreshData() {
            location.reload();
        }
        
        function searchIssues() {
            const searchInput = document.getElementById('search-input');
            currentSearch = searchInput.value.toLowerCase().trim();
            applyFilters();
        }
        
        function clearSearch() {
            document.getElementById('search-input').value = '';
            currentSearch = '';
            applyFilters();
        }
        
        function applyFilters() {
            const cards = document.querySelectorAll('.issue-card');
            const filterInfo = document.getElementById('filter-info');
            
            let visibleCount = 0;
            cards.forEach(card => {
                let showCard = true;
                
                if (currentSearch) {
                    const issueId = card.dataset.issueId || '';
                    const issueSubject = card.dataset.issueSubject || '';
                    
                    const matchesId = issueId.includes(currentSearch);
                    const matchesSubject = issueSubject.toLowerCase().includes(currentSearch);
                    
                    if (!matchesId && !matchesSubject) {
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
            
            let filterText = '';
            if (currentSearch) {
                filterText = `Search: "${currentSearch}" - Showing ${visibleCount} issues`;
            } else {
                filterText = `Showing ${visibleCount} issues`;
            }
            filterInfo.textContent = filterText;
        }
        
        // Auto-refresh every 60 seconds
        setInterval(refreshData, 60000);
    </script>
</body>
</html>
"""


def load_issue_pr_results():
    """Load issue-PR links from JSON file"""
    results_file = Path('issue_pr_links.json')
    if results_file.exists():
        try:
            with open(results_file, 'r') as f:
                data = json.load(f)
                
                # Filter to only show PRs with similarity > 0.85
                filtered_data = []
                for result in data:
                    filtered_prs = [
                        pr for pr in result.get('similar_prs', [])
                        if pr.get('similarity_score', 0) > 0.85
                    ]
                    if filtered_prs:  # Only include issues that have high-similarity PRs
                        result_copy = result.copy()
                        result_copy['similar_prs'] = filtered_prs
                        filtered_data.append(result_copy)
                
                # Limit to 50 issues per page
                return filtered_data[:50]
        except Exception as e:
            print(f"Error loading results: {e}")
            return []
    return []


@app.route('/')
def index():
    """Main page showing issue-PR links"""
    results = load_issue_pr_results()
    
    # Calculate stats
    total_issues = len(results)
    total_links = sum(len(r.get('similar_prs', [])) for r in results)
    
    return render_template_string(
        HTML_TEMPLATE,
        results=results,
        total_issues=total_issues,
        total_links=total_links,
        showing_count=total_issues
    )


@app.route('/api/results')
def api_results():
    """API endpoint to get results as JSON"""
    results = load_issue_pr_results()
    return jsonify({
        'success': True,
        'count': len(results),
        'results': results
    })


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Issue-PR Viewer')
    parser.add_argument('--port', type=int, default=5002,
                       help='Port to run server on (default: 5002)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind to (default: 0.0.0.0)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"🌐 Issue-PR Viewer Starting")
    print(f"{'='*60}")
    print(f"Server: http://localhost:{args.port}")
    print(f"\nShowing:")
    print(f"  - Redmine Issues → Similar GitHub PRs")
    print(f"  - Only PRs with similarity > 85%")
    print(f"  - Maximum 50 issues per page")
    print(f"{'='*60}\n")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()

# Made with Bob
