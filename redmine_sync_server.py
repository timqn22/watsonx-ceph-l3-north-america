#!/usr/bin/env python3
"""
Redmine Issue Sync Server
Continuously syncs new Redmine issues to the vector database
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict
import threading
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import IssuePipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('redmine_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask app for status/control
app = Flask(__name__)

# Global state
sync_state = {
    'running': False,
    'last_sync': None,
    'total_issues_synced': 0,
    'sync_interval_minutes': 15,
    'issues_per_sync': 10,
    'errors': []
}

sync_thread = None
stop_event = threading.Event()


class RedmineSyncServer:
    """Continuous Redmine issue synchronization service"""
    
    def __init__(self, sync_interval_minutes: int = 15, issues_per_sync: int = 10):
        self.sync_interval_minutes = sync_interval_minutes
        self.issues_per_sync = issues_per_sync
        
        # Get configuration from environment
        embedding_model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
        redmine_url = os.getenv('REDMINE_URL', 'https://tracker.ceph.com')
        redmine_api_key = os.getenv('REDMINE_API_KEY')
        
        self.pipeline = IssuePipeline(
            redmine_url=redmine_url,
            redmine_api_key=redmine_api_key,
            embedding_model=embedding_model
        )
        
        logger.info(f"Redmine Sync Server initialized (sync interval: {sync_interval_minutes} minutes, "
                   f"issues per sync: {issues_per_sync})")
    
    def run_sync(self) -> Dict:
        """Run a single sync cycle"""
        try:
            logger.info(f"Starting Redmine sync cycle (fetching {self.issues_per_sync} most recent issues)...")
            
            # Scrape recent issues
            stats = self.pipeline.scrape_and_index(
                max_issues=self.issues_per_sync,
                batch_size=self.issues_per_sync,
                delay=0.5,
                save_raw=False  # Don't save raw JSON files
            )
            
            # Update state
            sync_state['last_sync'] = datetime.now().isoformat()
            sync_state['total_issues_synced'] += stats.get('total_issues', 0)
            
            logger.info(f"Sync complete: {stats.get('total_issues', 0)} issues processed")
            
            return {
                'success': True,
                'issues_synced': stats.get('total_issues', 0),
                'timestamp': sync_state['last_sync'],
                'stats': stats
            }
            
        except Exception as e:
            error_msg = f"Error during sync: {str(e)}"
            logger.error(error_msg, exc_info=True)
            sync_state['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error': error_msg
            })
            # Keep only last 10 errors
            sync_state['errors'] = sync_state['errors'][-10:]
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    def run_continuous(self):
        """Run continuous sync loop"""
        logger.info("Starting continuous Redmine synchronization...")
        sync_state['running'] = True
        
        while not stop_event.is_set():
            try:
                # Run sync
                result = self.run_sync()
                
                if result['success']:
                    logger.info(f"Next sync in {self.sync_interval_minutes} minutes")
                else:
                    logger.warning(f"Sync failed, will retry in {self.sync_interval_minutes} minutes")
                
                # Wait for next interval (check stop_event every second)
                for _ in range(self.sync_interval_minutes * 60):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Unexpected error in sync loop: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying
        
        sync_state['running'] = False
        logger.info("Synchronization stopped")


# Flask API endpoints

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'redmine-sync',
        'running': sync_state['running']
    })


@app.route('/status', methods=['GET'])
def status():
    """Get sync status"""
    return jsonify({
        'running': sync_state['running'],
        'last_sync': sync_state['last_sync'],
        'total_issues_synced': sync_state['total_issues_synced'],
        'sync_interval_minutes': sync_state['sync_interval_minutes'],
        'issues_per_sync': sync_state['issues_per_sync'],
        'recent_errors': sync_state['errors'][-5:]  # Last 5 errors
    })


@app.route('/start', methods=['POST'])
def start_sync():
    """Start the sync service"""
    global sync_thread
    
    if sync_state['running']:
        return jsonify({
            'success': False,
            'message': 'Sync is already running'
        }), 400
    
    # Get parameters from request or use defaults
    data = request.get_json() or {}
    interval = data.get('interval_minutes', 15)
    issues_per_sync = data.get('issues_per_sync', 10)
    
    sync_state['sync_interval_minutes'] = interval
    sync_state['issues_per_sync'] = issues_per_sync
    
    # Start sync thread
    stop_event.clear()
    server = RedmineSyncServer(sync_interval_minutes=interval, issues_per_sync=issues_per_sync)
    sync_thread = threading.Thread(target=server.run_continuous, daemon=True)
    sync_thread.start()
    
    logger.info(f"Sync started via API (interval: {interval} minutes, issues per sync: {issues_per_sync})")
    
    return jsonify({
        'success': True,
        'message': f'Sync started (every {interval} minutes, {issues_per_sync} issues per sync)',
        'interval_minutes': interval,
        'issues_per_sync': issues_per_sync
    })


@app.route('/stop', methods=['POST'])
def stop_sync():
    """Stop the sync service"""
    if not sync_state['running']:
        return jsonify({
            'success': False,
            'message': 'Sync is not running'
        }), 400
    
    stop_event.set()
    logger.info("Sync stop requested via API")
    
    return jsonify({
        'success': True,
        'message': 'Sync stopped'
    })


@app.route('/sync-now', methods=['POST'])
def sync_now():
    """Trigger an immediate sync"""
    try:
        data = request.get_json() or {}
        issues_count = data.get('issues_count', sync_state['issues_per_sync'])
        
        server = RedmineSyncServer(
            sync_interval_minutes=sync_state['sync_interval_minutes'],
            issues_per_sync=issues_count
        )
        result = server.run_sync()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in manual sync: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/config', methods=['GET', 'POST'])
def config():
    """Get or update configuration"""
    if request.method == 'GET':
        return jsonify({
            'sync_interval_minutes': sync_state['sync_interval_minutes'],
            'issues_per_sync': sync_state['issues_per_sync']
        })
    else:
        data = request.get_json()
        if 'interval_minutes' in data:
            sync_state['sync_interval_minutes'] = data['interval_minutes']
            logger.info(f"Sync interval updated to {data['interval_minutes']} minutes")
        if 'issues_per_sync' in data:
            sync_state['issues_per_sync'] = data['issues_per_sync']
            logger.info(f"Issues per sync updated to {data['issues_per_sync']}")
        
        return jsonify({
            'success': True,
            'sync_interval_minutes': sync_state['sync_interval_minutes'],
            'issues_per_sync': sync_state['issues_per_sync']
        })


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Redmine Issue Sync Server')
    parser.add_argument('--port', type=int, default=8002,
                       help='Port to run server on (default: 8002)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--interval', type=int, default=15,
                       help='Sync interval in minutes (default: 15)')
    parser.add_argument('--issues', type=int, default=10,
                       help='Number of issues to sync per cycle (default: 10)')
    parser.add_argument('--autostart', action='store_true',
                       help='Automatically start syncing on server startup')
    
    args = parser.parse_args()
    
    # Auto-start sync if requested
    if args.autostart:
        logger.info(f"Auto-starting sync (interval: {args.interval} minutes, "
                   f"issues per sync: {args.issues})")
        sync_state['sync_interval_minutes'] = args.interval
        sync_state['issues_per_sync'] = args.issues
        stop_event.clear()
        server = RedmineSyncServer(sync_interval_minutes=args.interval, issues_per_sync=args.issues)
        sync_thread = threading.Thread(target=server.run_continuous, daemon=True)
        sync_thread.start()
    
    # Start Flask server
    logger.info(f"Starting Redmine Sync Server on {args.host}:{args.port}")
    print(f"\n{'='*60}")
    print(f"🔄 Redmine Sync Server Starting")
    print(f"{'='*60}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"Status: http://localhost:{args.port}/status")
    print(f"Health: http://localhost:{args.port}/health")
    print(f"\nAPI Endpoints:")
    print(f"  POST /start          - Start syncing")
    print(f"  POST /stop           - Stop syncing")
    print(f"  POST /sync-now       - Run immediate sync")
    print(f"  GET  /status         - Get sync status")
    print(f"  GET  /config         - Get configuration")
    print(f"  POST /config         - Update configuration")
    print(f"{'='*60}\n")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()

# Made with Bob
