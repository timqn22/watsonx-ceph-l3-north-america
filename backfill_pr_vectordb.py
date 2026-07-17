#!/usr/bin/env python3
"""
Backfill PR Vector Database
Loads existing PRs from pr_issue_links.json and adds them to the vector database
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pr_vector_store import PRVectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_prs():
    """Backfill PR vector database from existing pr_issue_links.json"""
    
    # Check if pr_issue_links.json exists
    pr_links_file = Path('pr_issue_links.json')
    if not pr_links_file.exists():
        logger.error("pr_issue_links.json not found! Run PR monitor first.")
        return
    
    # Load existing PR links
    logger.info("Loading existing PR links...")
    with open(pr_links_file, 'r') as f:
        pr_links = json.load(f)
    
    logger.info(f"Found {len(pr_links)} PRs in pr_issue_links.json")
    
    # Initialize PR vector store
    embedding_model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
    pr_vector_store = PRVectorStore(embedding_model=embedding_model)
    
    # Check current count
    current_count = pr_vector_store.count()
    logger.info(f"Current PR vector store has {current_count} PRs")
    
    # Add PRs to vector store
    added_count = 0
    skipped_count = 0
    
    for link in pr_links:
        pr_data = link.get('pr', {})
        if not pr_data:
            continue
        
        # Add body from search_text if available
        if 'search_text' in link and 'body' not in pr_data:
            # Extract body from search_text
            search_text = link['search_text']
            if 'Description:' in search_text:
                body = search_text.split('Description:')[1].split('Labels:')[0].strip()
                pr_data['body'] = body
        
        try:
            if pr_vector_store.add_pr(pr_data):
                added_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            logger.error(f"Error adding PR #{pr_data.get('pr_number')}: {e}")
    
    # Print summary
    final_count = pr_vector_store.count()
    
    print(f"\n{'='*60}")
    print(f"PR Vector Database Backfill Complete")
    print(f"{'='*60}")
    print(f"PRs in pr_issue_links.json: {len(pr_links)}")
    print(f"PRs added to vector store: {added_count}")
    print(f"PRs skipped (already exist): {skipped_count}")
    print(f"Total PRs in vector store: {final_count}")
    print(f"{'='*60}\n")
    
    logger.info("✅ Backfill complete!")


def main():
    """Main entry point"""
    backfill_prs()


if __name__ == '__main__':
    main()

# Made with Bob
