#!/usr/bin/env python3
"""
Simple HTTP API Server for Ceph Issue Search
Access via curl or browser - no fancy UI, just plain text/JSON results
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
from src.pipeline import IssuePipeline
from src.reranker import Reranker
from src.bm25_search import HybridSearch

# Initialize pipeline, reranker, and hybrid search
pipeline = None
reranker = None
hybrid_search = None

def get_pipeline():
    """Lazy load the pipeline"""
    global pipeline
    if pipeline is None:
        persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
        collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
        
        # Try to read from .env file first
        from dotenv import load_dotenv
        load_dotenv()
        
        embedding_model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
        
        print(f"Loading pipeline with model: {embedding_model}")
        print(f"Database location: {persist_dir}")
        pipeline = IssuePipeline(
            persist_directory=persist_dir,
            collection_name=collection_name,
            embedding_model=embedding_model
        )
        print("Pipeline loaded successfully!")
    return pipeline


def get_reranker():
    """Lazy load the reranker"""
    global reranker
    if reranker is None:
        # Try to read from .env file first
        from dotenv import load_dotenv
        load_dotenv()
        
        reranker_model = os.getenv('RERANKER_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
        enable_reranking = os.getenv('ENABLE_RERANKING', 'true').lower() == 'true'
        
        if enable_reranking:
            print(f"Loading reranker model: {reranker_model}")
            reranker = Reranker(model_name=reranker_model)
            print("Reranker loaded successfully!")
        else:
            print("Reranking disabled")
            reranker = None
    return reranker


def get_hybrid_search():
    """Lazy load the hybrid search"""
    global hybrid_search
    if hybrid_search is None:
        # Try to read from .env file first
        from dotenv import load_dotenv
        load_dotenv()
        
        enable_hybrid = os.getenv('ENABLE_HYBRID_SEARCH', 'true').lower() == 'true'
        semantic_weight = float(os.getenv('SEMANTIC_WEIGHT', '0.9'))
        bm25_weight = float(os.getenv('BM25_WEIGHT', '0.1'))
        
        if enable_hybrid:
            try:
                print(f"Initializing hybrid search: {semantic_weight*100}% semantic, {bm25_weight*100}% BM25")
                hybrid_search = HybridSearch(semantic_weight=semantic_weight, bm25_weight=bm25_weight)
                
                # Index all documents from the vector store
                pipeline = get_pipeline()
                print("Indexing documents for BM25...")
                
                # Get all documents from ChromaDB
                collection = pipeline.vector_store.collection
                all_data = collection.get(include=['documents', 'metadatas'])
                
                if all_data['ids'] and all_data['documents'] and all_data['metadatas']:
                    hybrid_search.index_documents(
                        all_data['ids'],
                        all_data['documents'],
                        all_data['metadatas']
                    )
                    print(f"Indexed {len(all_data['ids'])} documents for BM25 hybrid search")
                else:
                    print("No documents found to index for BM25")
                
            except ImportError:
                print("rank-bm25 not installed. Hybrid search disabled. Install with: pip install rank-bm25")
                hybrid_search = None
            except Exception as e:
                print(f"Error initializing hybrid search: {e}")
                hybrid_search = None
        else:
            print("Hybrid search disabled")
            hybrid_search = None
    return hybrid_search


class SearchHandler(BaseHTTPRequestHandler):
    """HTTP request handler for search API"""
    
    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[{self.log_date_time_string()}] {format % args}")
    
    def _set_cors_headers(self):
        """Set CORS headers for all responses"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)
        
        # Root endpoint - show usage
        if path == '/' or path == '':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self._set_cors_headers()
            self.end_headers()
            
            usage = """Ceph Issue Search API
======================

Usage:
------

1. Search for issues:
   curl "http://localhost:8000/search?q=OSD+crash&limit=10"
   
   Or in browser:
   http://localhost:8000/search?q=OSD+crash&limit=10

2. Find similar issues:
   curl "http://localhost:8000/similar/78000?limit=10"
   
   Or in browser:
   http://localhost:8000/similar/78000?limit=10

3. Get related PRs for an issue (for browser extension):
   curl "http://localhost:8000/issues/78000/related-prs"
   
   Or in browser:
   http://localhost:8000/issues/78000/related-prs

4. Get statistics:
   curl "http://localhost:8000/stats"
   
   Or in browser:
   http://localhost:8000/stats

5. Health check:
   curl "http://localhost:8000/health"

Parameters:
-----------
- q: Search query (required for /search)
- limit: Number of results (default: 10)
- format: Response format - 'json' or 'text' (default: text)

Examples:
---------
curl "http://localhost:8000/search?q=memory+leak&limit=5"
curl "http://localhost:8000/search?q=OSD+crash&format=json"
curl "http://localhost:8000/similar/78000?limit=10&format=json"
curl "http://localhost:8000/issues/78000/related-prs"

Browser Extension:
------------------
The /issues/{id}/related-prs endpoint is used by the TrackerAssist
browser extension to show related PRs on Redmine issue pages.
See extension/README.md for installation instructions.

Access from anywhere:
--------------------
Replace 'localhost' with your machine's IP address
Example: http://192.168.1.100:8000/search?q=crash
"""
            self.wfile.write(usage.encode())
            return
        
        # Search endpoint
        elif path == '/search':
            query = params.get('q', [''])[0]
            if not query:
                self.send_error(400, "Missing 'q' parameter")
                return
            
            limit = int(params.get('limit', ['10'])[0])
            format_type = params.get('format', ['text'])[0]
            
            try:
                pipeline = get_pipeline()
                reranker = get_reranker()
                hybrid_search = get_hybrid_search()
                
                # Fetch more results for reranking if reranker is enabled
                fetch_limit = limit * 3 if reranker else limit
                results = pipeline.search_similar_issues(query, n_results=fetch_limit)
                
                # Apply hybrid search (BM25 + semantic) if enabled
                if hybrid_search and results:
                    print(f"Applying hybrid search to {len(results)} results...")
                    results = hybrid_search.combine_scores(
                        results,
                        query,
                        n_results=fetch_limit
                    )
                    print(f"Hybrid search complete")
                
                # Apply reranking if enabled
                if reranker and results:
                    print(f"Reranking {len(results)} results...")
                    results = reranker.rerank(
                        query=query,
                        results=results,
                        top_k=limit
                    )
                    print(f"Reranking complete. Returning top {len(results)} results")
                
                if format_type == 'json':
                    self.send_json_response(results)
                else:
                    self.send_text_response(results, query)
            
            except Exception as e:
                self.send_error(500, f"Search failed: {str(e)}")
        
        # Similar issues endpoint
        elif path.startswith('/similar/'):
            issue_id = path.split('/')[-1]
            limit = int(params.get('limit', ['10'])[0])
            format_type = params.get('format', ['text'])[0]
            
            try:
                pipeline = get_pipeline()
                reranker = get_reranker()
                
                # Fetch more results for reranking if reranker is enabled
                fetch_limit = limit * 3 if reranker else limit
                results = pipeline.find_similar_to_issue(issue_id, n_results=fetch_limit)
                
                # Apply reranking if enabled
                if reranker and results:
                    # Get the source issue text for reranking
                    source_issue = pipeline.vector_store.get_issue(issue_id)
                    if source_issue:
                        query = source_issue['document']
                        print(f"Reranking {len(results)} results for issue #{issue_id}...")
                        results = reranker.rerank(
                            query=query,
                            results=results,
                            top_k=limit
                        )
                        print(f"Reranking complete. Returning top {len(results)} results")
                
                if format_type == 'json':
                    self.send_json_response(results)
                else:
                    self.send_text_response(results, f"Similar to #{issue_id}")
            
            except Exception as e:
                self.send_error(500, f"Search failed: {str(e)}")
        
        # Stats endpoint
        elif path == '/stats':
            try:
                pipeline = get_pipeline()
                stats = pipeline.get_stats()
                
                format_type = params.get('format', ['text'])[0]
                if format_type == 'json':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps(stats, indent=2).encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self._set_cors_headers()
                    self.end_headers()
                    
                    vs = stats['vector_store']
                    text = f"""Database Statistics
===================

Total Issues: {vs['total_issues']}
Collection: {vs['collection_name']}
Embedding Model: {vs['embedding_model']}
Embedding Dimensions: {vs['embedding_dimension']}
Database Location: {vs['persist_directory']}
"""
                    self.wfile.write(text.encode())
            
            except Exception as e:
                self.send_error(500, f"Stats failed: {str(e)}")
        
        # Health check
        elif path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(b"OK")
        
        # Related PRs for an issue (for browser extension)
        elif path.startswith('/issues/') and path.endswith('/related-prs'):
            issue_id = path.split('/')[-2]
            try:
                # Load issue_pr_links.json
                with open('issue_pr_links.json', 'r') as f:
                    issue_pr_data = json.load(f)
                
                # Find the issue
                related_prs = []
                for item in issue_pr_data:
                    if str(item['issue']['issue_id']) == str(issue_id):
                        # Format PRs for the extension
                        for pr in item.get('similar_prs', []):
                            related_prs.append({
                                'pr_number': pr['pr_number'],
                                'title': pr['metadata'].get('title', ''),
                                'url': pr['metadata'].get('url', ''),
                                'state': pr['metadata'].get('state', 'unknown'),
                                'labels': pr['metadata'].get('labels', ''),
                                'author': pr['metadata'].get('author', ''),
                                'similarity_score': pr.get('similarity_score', 0),
                                'repo': 'ceph/ceph'  # Default repo
                            })
                        break
                
                self.send_json_response(related_prs)
            
            except FileNotFoundError:
                self.send_error(404, "issue_pr_links.json not found. Run generate_issue_pr_links.py first.")
            except Exception as e:
                self.send_error(500, f"Failed to load related PRs: {str(e)}")
        
        else:
            self.send_error(404, "Endpoint not found")
    
    def send_json_response(self, results):
        """Send JSON response"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(results, indent=2).encode())
    
    def send_text_response(self, results, query):
        """Send plain text response"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self._set_cors_headers()
        self.end_headers()
        
        output = f"Search Results for: {query}\n"
        output += "=" * 80 + "\n\n"
        
        if not results:
            output += "No results found.\n"
        else:
            for i, result in enumerate(results, 1):
                metadata = result['metadata']
                similarity = result['similarity_score']
                
                output += f"{i}. Issue #{metadata['issue_id']} (similarity: {similarity:.3f})\n"
                output += f"   Subject: {metadata['subject']}\n"
                output += f"   Status: {metadata['status']} | Priority: {metadata['priority']}\n"
                output += f"   URL: {metadata['url']}\n"
                
                # Add preview of content
                doc = result.get('document', '')
                if doc:
                    preview = doc[:200].replace('\n', ' ')
                    output += f"   Preview: {preview}...\n"
                
                output += "\n"
        
        output += f"\nTotal results: {len(results)}\n"
        self.wfile.write(output.encode('utf-8'))


def run_server(port=8000, host='0.0.0.0'):
    """Run the HTTP server"""
    server_address = (host, port)
    httpd = HTTPServer(server_address, SearchHandler)
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          Ceph Issue Search API Server                        ║
╚══════════════════════════════════════════════════════════════╝

Server running on: http://{host}:{port}

Local access:
  http://localhost:{port}/search?q=OSD+crash

Network access (from other devices):
  http://YOUR_IP_ADDRESS:{port}/search?q=OSD+crash

Examples:
  curl "http://localhost:{port}/search?q=memory+leak&limit=5"
  curl "http://localhost:{port}/similar/78000?limit=10"
  curl "http://localhost:{port}/stats"

Press Ctrl+C to stop the server
""")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()


if __name__ == '__main__':
    import sys
    
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    run_server(port=port)

# Made with Bob
