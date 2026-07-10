"""
Flask REST API for Ceph Tracker Linker
Exposes scrapers, embeddings, and recommendations via HTTP
"""
import os
import sys
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config
from scrapers import CephTrackerScraper, GithubPRScraper
from embeddings import SentenceTransformerEmbedder
from similarity import SimilarityCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load configuration
config = get_config()
app.config.from_object(config)

# Initialize components (lazy loading)
_embedder = None
_calculator = None


def get_embedder():
    """Get or create embedder instance"""
    global _embedder
    if _embedder is None:
        model_name = app.config.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        cache_dir = app.config.get('EMBEDDING_CACHE_DIR', './models')
        _embedder = SentenceTransformerEmbedder(model_name=model_name, cache_dir=cache_dir)
        logger.info(f"Embedder initialized: {model_name}")
    return _embedder


def get_calculator():
    """Get or create similarity calculator instance"""
    global _calculator
    if _calculator is None:
        threshold = app.config.get('SIMILARITY_THRESHOLD', 0.75)
        _calculator = SimilarityCalculator(threshold=threshold)
        logger.info(f"Calculator initialized with threshold: {threshold}")
    return _calculator


# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'ceph-tracker-linker',
        'version': '1.0.0'
    })


# Status endpoint
@app.route('/status', methods=['GET'])
def status():
    """Detailed status endpoint"""
    try:
        embedder = get_embedder()
        calculator = get_calculator()
        
        return jsonify({
            'status': 'ok',
            'service': 'ceph-tracker-linker',
            'version': '1.0.0',
            'embedder': embedder.get_model_info(),
            'similarity_threshold': calculator.get_threshold(),
            'config': {
                'ceph_tracker_url': app.config.get('CEPH_TRACKER_URL'),
                'github_repo': app.config.get('GITHUB_REPO'),
                'max_recommendations': app.config.get('MAX_RECOMMENDATIONS')
            }
        })
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Scraper endpoints
@app.route('/api/trackers', methods=['GET'])
def get_trackers():
    """Get unlinked trackers from Ceph tracker"""
    try:
        limit = request.args.get('limit', default=10, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        base_url = app.config.get('CEPH_TRACKER_URL')
        project_id = app.config.get('CEPH_PROJECT_ID')
        
        with CephTrackerScraper(base_url=base_url, project_id=project_id) as scraper:
            trackers = scraper.fetch_unlinked_trackers(limit=limit, offset=offset)
        
        return jsonify({
            'success': True,
            'count': len(trackers),
            'trackers': trackers
        })
    except Exception as e:
        logger.error(f"Error fetching trackers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trackers/<int:tracker_id>', methods=['GET'])
def get_tracker(tracker_id):
    """Get specific tracker by ID"""
    try:
        base_url = app.config.get('CEPH_TRACKER_URL')
        
        with CephTrackerScraper(base_url=base_url) as scraper:
            tracker = scraper.fetch_tracker(tracker_id)
        
        if tracker:
            return jsonify({'success': True, 'tracker': tracker})
        else:
            return jsonify({'success': False, 'error': 'Tracker not found'}), 404
    except Exception as e:
        logger.error(f"Error fetching tracker {tracker_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/prs', methods=['GET'])
def get_prs():
    """Get unlinked PRs from GitHub"""
    try:
        limit = request.args.get('limit', default=10, type=int)
        state = request.args.get('state', default='open', type=str)
        
        github_token = app.config.get('GITHUB_TOKEN')
        repo = app.config.get('GITHUB_REPO')
        
        with GithubPRScraper(access_token=github_token, repo=repo) as scraper:
            prs = scraper.fetch_unlinked_prs(state=state, limit=limit)
        
        return jsonify({
            'success': True,
            'count': len(prs),
            'prs': prs
        })
    except Exception as e:
        logger.error(f"Error fetching PRs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/prs/<int:pr_number>', methods=['GET'])
def get_pr(pr_number):
    """Get specific PR by number"""
    try:
        github_token = app.config.get('GITHUB_TOKEN')
        repo = app.config.get('GITHUB_REPO')
        
        with GithubPRScraper(access_token=github_token, repo=repo) as scraper:
            pr = scraper.fetch_pr(pr_number)
        
        if pr:
            return jsonify({'success': True, 'pr': pr})
        else:
            return jsonify({'success': False, 'error': 'PR not found'}), 404
    except Exception as e:
        logger.error(f"Error fetching PR {pr_number}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Embedding endpoints
@app.route('/api/embeddings/generate', methods=['POST'])
def generate_embeddings():
    """Generate embeddings for texts"""
    try:
        data = request.get_json()
        texts = data.get('texts', [])
        
        if not texts:
            return jsonify({'success': False, 'error': 'No texts provided'}), 400
        
        embedder = get_embedder()
        embeddings = embedder.generate_embeddings(texts)
        
        return jsonify({
            'success': True,
            'count': len(embeddings),
            'embeddings': embeddings.tolist(),
            'dimension': embedder.get_embedding_dimension()
        })
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Recommendation endpoints
@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get all recommendations"""
    try:
        tracker_limit = request.args.get('tracker_limit', default=10, type=int)
        pr_limit = request.args.get('pr_limit', default=50, type=int)
        top_k = request.args.get('top_k', default=5, type=int)
        
        # Fetch data
        base_url = app.config.get('CEPH_TRACKER_URL')
        project_id = app.config.get('CEPH_PROJECT_ID')
        github_token = app.config.get('GITHUB_TOKEN')
        repo = app.config.get('GITHUB_REPO')
        
        with CephTrackerScraper(base_url=base_url, project_id=project_id) as scraper:
            trackers = scraper.fetch_unlinked_trackers(limit=tracker_limit)
        
        with GithubPRScraper(access_token=github_token, repo=repo) as scraper:
            prs = scraper.fetch_unlinked_prs(limit=pr_limit)
        
        if not trackers or not prs:
            return jsonify({
                'success': True,
                'recommendations': [],
                'message': 'No unlinked trackers or PRs found'
            })
        
        # Generate embeddings
        embedder = get_embedder()
        tracker_texts = [t['combined_text'] for t in trackers]
        pr_texts = [p['combined_text'] for p in prs]
        
        tracker_embeddings = embedder.generate_embeddings(tracker_texts)
        pr_embeddings = embedder.generate_embeddings(pr_texts)
        
        # Calculate similarities and generate recommendations
        calculator = get_calculator()
        recommendations = []
        
        for i, tracker in enumerate(trackers):
            matches = calculator.find_top_matches(
                tracker_embeddings[i],
                pr_embeddings,
                prs,
                top_k=top_k
            )
            
            for pr, score in matches:
                recommendations.append({
                    'tracker': tracker,
                    'pr': pr,
                    'similarity': float(score),
                    'confidence': calculator.get_confidence_level(score)
                })
        
        # Sort by similarity
        recommendations.sort(key=lambda x: x['similarity'], reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(recommendations),
            'recommendations': recommendations
        })
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recommendations/tracker/<int:tracker_id>', methods=['GET'])
def get_tracker_recommendations(tracker_id):
    """Get recommendations for a specific tracker"""
    try:
        top_k = request.args.get('top_k', default=10, type=int)
        pr_limit = request.args.get('pr_limit', default=100, type=int)
        
        # Fetch tracker
        base_url = app.config.get('CEPH_TRACKER_URL')
        with CephTrackerScraper(base_url=base_url) as scraper:
            tracker = scraper.fetch_tracker(tracker_id)
        
        if not tracker:
            return jsonify({'success': False, 'error': 'Tracker not found'}), 404
        
        # Fetch PRs
        github_token = app.config.get('GITHUB_TOKEN')
        repo = app.config.get('GITHUB_REPO')
        with GithubPRScraper(access_token=github_token, repo=repo) as scraper:
            prs = scraper.fetch_unlinked_prs(limit=pr_limit)
        
        if not prs:
            return jsonify({
                'success': True,
                'tracker': tracker,
                'recommendations': [],
                'message': 'No unlinked PRs found'
            })
        
        # Generate embeddings
        embedder = get_embedder()
        tracker_embedding = embedder.generate_embedding(tracker['combined_text'])
        pr_texts = [p['combined_text'] for p in prs]
        pr_embeddings = embedder.generate_embeddings(pr_texts)
        
        # Find matches
        calculator = get_calculator()
        matches = calculator.find_top_matches(
            tracker_embedding,
            pr_embeddings,
            prs,
            top_k=top_k
        )
        
        recommendations = [
            {
                'pr': pr,
                'similarity': float(score),
                'confidence': calculator.get_confidence_level(score)
            }
            for pr, score in matches
        ]
        
        return jsonify({
            'success': True,
            'tracker': tracker,
            'count': len(recommendations),
            'recommendations': recommendations
        })
    except Exception as e:
        logger.error(f"Error getting recommendations for tracker {tracker_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


if __name__ == '__main__':
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', False)
    
    logger.info(f"Starting Ceph Tracker Linker API on {host}:{port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(host=host, port=port, debug=debug)

# Made with Bob
