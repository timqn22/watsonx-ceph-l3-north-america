#!/usr/bin/env python3
"""
GitHub PR Monitoring Server
Runs continuously as a background service, monitoring PRs and finding similar issues.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import threading
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.github_monitor import GitHubPRMonitor, PRIssueLinker
from src.pipeline import IssuePipeline
from src.pr_vector_store import PRVectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pr_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask app for status/control
app = Flask(__name__)

# Global state
monitor_state = {
    'running': False,
    'last_check': None,
    'total_prs_processed': 0,
    'total_links_found': 0,
    'check_interval_minutes': 15,
    'errors': []
}

monitor_thread = None
stop_event = threading.Event()


class PRMonitorServer:
    """Continuous PR monitoring service"""
    
    def __init__(self, check_interval_minutes: int = 15, initial_pr_count: int = 10):
        self.check_interval_minutes = check_interval_minutes
        self.initial_pr_count = initial_pr_count
        
        # Get configuration from environment
        github_token = os.getenv('GITHUB_TOKEN')
        embedding_model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
        
        self.github_monitor = GitHubPRMonitor(github_token=github_token)
        self.pipeline = IssuePipeline(embedding_model=embedding_model)
        self.pr_vector_store = PRVectorStore(embedding_model=embedding_model)
        self.linker = PRIssueLinker(self.pipeline, self.github_monitor, self.pr_vector_store)
        self.is_first_run = len(self.linker.seen_prs) == 0
        
        logger.info(f"PR Monitor Server initialized (check interval: {check_interval_minutes} minutes)")
        if self.is_first_run:
            logger.info(f"First run detected - will process {initial_pr_count} most recent PRs")
    
    def run_check(self) -> Dict:
        """Run a single PR check cycle"""
        try:
            logger.info("Starting PR check cycle...")
            
            # First run: only process N most recent PRs
            if self.is_first_run:
                logger.info(f"First run - processing {self.initial_pr_count} most recent PRs only")
                results = self.linker.initialize_with_recent_prs(max_prs=self.initial_pr_count)
                self.is_first_run = False
            else:
                # Subsequent runs: check for new PRs since last check
                minutes_back = self.check_interval_minutes
                if monitor_state['last_check']:
                    # Calculate minutes since last check
                    last_check_time = datetime.fromisoformat(monitor_state['last_check'])
                    minutes_back = int((datetime.now() - last_check_time).total_seconds() / 60) + 5  # +5 buffer
                
                # Find and link PRs
                results = self.linker.process_new_prs(
                    since_minutes=minutes_back
                )
            
            # Update state
            monitor_state['last_check'] = datetime.now().isoformat()
            monitor_state['total_prs_processed'] += len(results)
            monitor_state['total_links_found'] += sum(len(r['similar_issues']) for r in results)
            
            logger.info(f"Check complete: {len(results)} PRs processed, "
                       f"{sum(len(r['similar_issues']) for r in results)} links found")
            
            return {
                'success': True,
                'prs_processed': len(results),
                'links_found': sum(len(r['similar_issues']) for r in results),
                'timestamp': monitor_state['last_check']
            }
            
        except Exception as e:
            error_msg = f"Error during PR check: {str(e)}"
            logger.error(error_msg, exc_info=True)
            monitor_state['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error': error_msg
            })
            # Keep only last 10 errors
            monitor_state['errors'] = monitor_state['errors'][-10:]
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    def run_continuous(self):
        """Run continuous monitoring loop"""
        logger.info("Starting continuous monitoring...")
        monitor_state['running'] = True
        
        while not stop_event.is_set():
            try:
                # Run check
                result = self.run_check()
                
                if result['success']:
                    logger.info(f"Next check in {self.check_interval_minutes} minutes")
                else:
                    logger.warning(f"Check failed, will retry in {self.check_interval_minutes} minutes")
                
                # Wait for next interval (check stop_event every second)
                for _ in range(self.check_interval_minutes * 60):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Unexpected error in monitoring loop: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying
        
        monitor_state['running'] = False
        logger.info("Monitoring stopped")


# Flask API endpoints

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'pr-monitor',
        'running': monitor_state['running']
    })


@app.route('/status', methods=['GET'])
def status():
    """Get monitoring status"""
    return jsonify({
        'running': monitor_state['running'],
        'last_check': monitor_state['last_check'],
        'total_prs_processed': monitor_state['total_prs_processed'],
        'total_links_found': monitor_state['total_links_found'],
        'check_interval_minutes': monitor_state['check_interval_minutes'],
        'recent_errors': monitor_state['errors'][-5:]  # Last 5 errors
    })


@app.route('/start', methods=['POST'])
def start_monitoring():
    """Start the monitoring service"""
    global monitor_thread
    
    if monitor_state['running']:
        return jsonify({
            'success': False,
            'message': 'Monitoring is already running'
        }), 400
    
    # Get interval from request or use default
    data = request.get_json() or {}
    interval = data.get('interval_minutes', 15)
    initial_count = data.get('initial_pr_count', 10)
    monitor_state['check_interval_minutes'] = interval
    
    # Start monitoring thread
    stop_event.clear()
    server = PRMonitorServer(check_interval_minutes=interval, initial_pr_count=initial_count)
    monitor_thread = threading.Thread(target=server.run_continuous, daemon=True)
    monitor_thread.start()
    
    logger.info(f"Monitoring started via API (interval: {interval} minutes)")
    
    return jsonify({
        'success': True,
        'message': f'Monitoring started (checking every {interval} minutes)',
        'interval_minutes': interval
    })


@app.route('/stop', methods=['POST'])
def stop_monitoring():
    """Stop the monitoring service"""
    if not monitor_state['running']:
        return jsonify({
            'success': False,
            'message': 'Monitoring is not running'
        }), 400
    
    stop_event.set()
    logger.info("Monitoring stop requested via API")
    
    return jsonify({
        'success': True,
        'message': 'Monitoring stopped'
    })


@app.route('/check-now', methods=['POST'])
def check_now():
    """Trigger an immediate PR check"""
    try:
        server = PRMonitorServer(check_interval_minutes=monitor_state['check_interval_minutes'])
        result = server.run_check()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in manual check: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/results', methods=['GET'])
def get_results():
    """Get latest PR-issue links"""
    try:
        results_file = Path('pr_issue_links.json')
        if not results_file.exists():
            return jsonify({
                'success': False,
                'message': 'No results found yet'
            }), 404
        
        with open(results_file, 'r') as f:
            data = json.load(f)
        
        # Optional: filter by limit
        limit = request.args.get('limit', type=int)
        if limit:
            data = data[:limit]
        
        return jsonify({
            'success': True,
            'count': len(data),
            'results': data
        })
    except Exception as e:
        logger.error(f"Error reading results: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/config', methods=['GET', 'POST'])
def config():
    """Get or update configuration"""
    if request.method == 'GET':
        return jsonify({
            'check_interval_minutes': monitor_state['check_interval_minutes']
        })
    else:
        data = request.get_json()
        if 'interval_minutes' in data:
            monitor_state['check_interval_minutes'] = data['interval_minutes']
            logger.info(f"Check interval updated to {data['interval_minutes']} minutes")
        
        return jsonify({
            'success': True,
            'check_interval_minutes': monitor_state['check_interval_minutes']
        })


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GitHub PR Monitoring Server')
    parser.add_argument('--port', type=int, default=8001,
                       help='Port to run server on (default: 8001)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--interval', type=int, default=15,
                       help='Check interval in minutes (default: 15)')
    parser.add_argument('--autostart', action='store_true',
                       help='Automatically start monitoring on server startup')
    parser.add_argument('--initial-prs', type=int, default=10,
                       help='Number of recent PRs to process on first run (default: 10)')
    
    args = parser.parse_args()
    
    # Auto-start monitoring if requested
    if args.autostart:
        logger.info(f"Auto-starting monitoring (interval: {args.interval} minutes)")
        logger.info(f"First run will process {args.initial_prs} most recent PRs")
        monitor_state['check_interval_minutes'] = args.interval
        stop_event.clear()
        server = PRMonitorServer(check_interval_minutes=args.interval, initial_pr_count=args.initial_prs)
        monitor_thread = threading.Thread(target=server.run_continuous, daemon=True)
        monitor_thread.start()
    
    # Start Flask server
    logger.info(f"Starting PR Monitor Server on {args.host}:{args.port}")
    print(f"\n{'='*60}")
    print(f"🚀 PR Monitor Server Starting")
    print(f"{'='*60}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"Status: http://localhost:{args.port}/status")
    print(f"Health: http://localhost:{args.port}/health")
    print(f"\nAPI Endpoints:")
    print(f"  POST /start          - Start monitoring")
    print(f"  POST /stop           - Stop monitoring")
    print(f"  POST /check-now      - Run immediate check")
    print(f"  GET  /status         - Get monitoring status")
    print(f"  GET  /results        - Get PR-issue links")
    print(f"  GET  /config         - Get configuration")
    print(f"  POST /config         - Update configuration")
    print(f"{'='*60}\n")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()

# Made with Bob
