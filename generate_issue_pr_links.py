#!/usr/bin/env python3
"""
Generate Issue-to-PR Links
Creates reverse mappings: for each recent Redmine issue, find similar GitHub PRs
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import IssuePipeline
from src.pr_vector_store import PRVectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_issue_pr_links(max_issues: int = 50, top_k_prs: int = 10):
    """
    Generate issue-to-PR links for recent issues
    
    Args:
        max_issues: Number of recent issues to process
        top_k_prs: Number of similar PRs to find for each issue
    """
    logger.info(f"Generating issue-PR links for {max_issues} most recent issues...")
    
    # Get configuration
    embedding_model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
    
    # Initialize stores
    issue_pipeline = IssuePipeline(embedding_model=embedding_model)
    pr_vector_store = PRVectorStore(embedding_model=embedding_model)
    
    # Check if we have PRs
    pr_count = pr_vector_store.count()
    if pr_count == 0:
        logger.error("No PRs found in vector store. Run PR monitor first!")
        return
    
    logger.info(f"Found {pr_count} PRs in vector store")
    
    # Get recent issues from the vector store
    logger.info("Fetching recent issues...")
    try:
        # Get all issue IDs and sort to get most recent
        collection = issue_pipeline.vector_store.collection
        all_results = collection.get()
        
        if not all_results['ids']:
            logger.error("No issues found in vector store!")
            return
        
        # Sort by issue ID (descending) to get most recent
        issue_ids = sorted([int(id) for id in all_results['ids']], reverse=True)
        recent_issue_ids = issue_ids[:max_issues]
        
        logger.info(f"Processing {len(recent_issue_ids)} recent issues...")
        
        # Generate links
        issue_pr_links = []
        
        for issue_id in recent_issue_ids:
            try:
                # Get issue details
                issue_result = collection.get(ids=[str(issue_id)])
                if not issue_result['ids']:
                    continue
                
                issue_text = issue_result['documents'][0]
                issue_metadata = issue_result['metadatas'][0]
                
                logger.info(f"Processing issue #{issue_id}: {issue_metadata.get('subject', 'N/A')}")
                
                # Search for similar PRs
                similar_prs = pr_vector_store.search_similar_prs(
                    query=issue_text,
                    n_results=top_k_prs
                )
                
                if similar_prs:
                    link_entry = {
                        'issue': {
                            'issue_id': issue_id,
                            'subject': issue_metadata.get('subject', ''),
                            'status': issue_metadata.get('status', ''),
                            'priority': issue_metadata.get('priority', ''),
                            'url': issue_metadata.get('url', f'https://tracker.ceph.com/issues/{issue_id}')
                        },
                        'similar_prs': similar_prs
                    }
                    issue_pr_links.append(link_entry)
                    logger.info(f"  Found {len(similar_prs)} similar PRs")
                
            except Exception as e:
                logger.error(f"Error processing issue #{issue_id}: {e}")
                continue
        
        # Save results
        output_file = Path('issue_pr_links.json')
        with open(output_file, 'w') as f:
            json.dump(issue_pr_links, f, indent=2)
        
        logger.info(f"✅ Generated {len(issue_pr_links)} issue-PR links")
        logger.info(f"📁 Saved to {output_file}")
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Issue-PR Link Generation Complete")
        print(f"{'='*60}")
        print(f"Issues processed: {len(issue_pr_links)}")
        print(f"Total PR links: {sum(len(link['similar_prs']) for link in issue_pr_links)}")
        print(f"Output file: {output_file}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"Error generating links: {e}", exc_info=True)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Issue-to-PR Links')
    parser.add_argument('--issues', type=int, default=50,
                       help='Number of recent issues to process (default: 50)')
    parser.add_argument('--top-k', type=int, default=10,
                       help='Number of similar PRs per issue (default: 10)')
    
    args = parser.parse_args()
    
    generate_issue_pr_links(max_issues=args.issues, top_k_prs=args.top_k)


if __name__ == '__main__':
    main()

# Made with Bob
