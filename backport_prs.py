#!/usr/bin/env python3
"""
Backport PRs - Fetch Historical PRs and Link to Issues
Fetches the last N PRs from GitHub, adds them to PR vector database,
and links them to similar Redmine issues.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_prs_paginated(monitor: GitHubPRMonitor, max_prs: int = 1000) -> List[Dict]:
    """
    Fetch PRs using pagination to get more than 100
    
    Args:
        monitor: GitHubPRMonitor instance
        max_prs: Maximum number of PRs to fetch
    
    Returns:
        List of PR dictionaries
    """
    all_prs = []
    page = 1
    per_page = 100  # GitHub's max per page
    
    logger.info(f"Fetching up to {max_prs} PRs from GitHub...")
    
    while len(all_prs) < max_prs:
        url = f"{monitor.base_url}/repos/{monitor.repo_owner}/{monitor.repo_name}/pulls"
        params = {
            'state': 'all',  # Get both open and closed
            'sort': 'created',
            'direction': 'desc',
            'per_page': per_page,
            'page': page
        }
        
        try:
            logger.info(f"Fetching page {page} (PRs {len(all_prs)}-{len(all_prs) + per_page})...")
            response = monitor.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            prs = response.json()
            
            if not prs:
                logger.info("No more PRs to fetch")
                break
            
            all_prs.extend(prs)
            logger.info(f"Fetched {len(prs)} PRs (total: {len(all_prs)})")
            
            # Check if we've reached the limit
            if len(all_prs) >= max_prs:
                all_prs = all_prs[:max_prs]
                break
            
            page += 1
            
        except Exception as e:
            logger.error(f"Error fetching page {page}: {e}")
            break
    
    logger.info(f"Total PRs fetched: {len(all_prs)}")
    return all_prs


def process_pr_batch(
    prs: List[Dict],
    linker: PRIssueLinker,
    monitor: GitHubPRMonitor,
    pr_vector_store: PRVectorStore,
    batch_size: int = 10
) -> List[Dict]:
    """
    Process a batch of PRs: add to vector store and link to issues
    
    Args:
        prs: List of PR dictionaries
        linker: PRIssueLinker instance
        monitor: GitHubPRMonitor instance
        pr_vector_store: PRVectorStore instance
        batch_size: Number of PRs to process before saving
    
    Returns:
        List of PR-issue link dictionaries
    """
    results = []
    
    for i, pr in enumerate(prs, 1):
        pr_number = pr['number']
        
        # Skip if already processed
        if pr_number in linker.seen_prs:
            logger.info(f"[{i}/{len(prs)}] PR #{pr_number} already processed, skipping")
            continue
        
        try:
            logger.info(f"[{i}/{len(prs)}] Processing PR #{pr_number}: {pr['title'][:60]}...")
            
            # Extract metadata
            metadata = monitor.extract_pr_metadata(pr)
            
            # Format for search
            search_text = monitor.format_pr_for_search(pr)
            
            # Add to PR vector store
            pr_data = {
                'pr_number': pr_number,
                'title': pr['title'],
                'body': pr.get('body', ''),
                'state': pr['state'],
                'author': pr['user']['login'],
                'created_at': pr['created_at'],
                'url': pr['html_url'],
                'labels': [label['name'] for label in pr.get('labels', [])]
            }
            
            added = pr_vector_store.add_pr(pr_data)
            if added:
                logger.info(f"  ✓ Added PR #{pr_number} to vector store")
            else:
                logger.info(f"  - PR #{pr_number} already in vector store")
            
            # Find similar issues
            similar_issues = linker.find_similar_issues(pr, n_results=10)
            
            if similar_issues:
                logger.info(f"  ✓ Found {len(similar_issues)} similar issues")
                
                # Create result entry
                result = {
                    'pr': metadata,
                    'search_text': search_text,
                    'similar_issues': similar_issues,
                    'processed_at': datetime.utcnow().isoformat()
                }
                results.append(result)
            else:
                logger.info(f"  - No similar issues found")
            
            # Mark as seen
            linker.seen_prs.add(pr_number)
            
            # Save progress periodically
            if i % batch_size == 0:
                logger.info(f"Saving progress... ({i}/{len(prs)} PRs processed)")
                save_results(results, linker)
        
        except Exception as e:
            logger.error(f"Error processing PR #{pr_number}: {e}")
            continue
    
    return results


def save_results(results: List[Dict], linker: PRIssueLinker):
    """Save results to file"""
    # Load existing results
    existing_results = []
    if linker.results_file.exists():
        try:
            with open(linker.results_file, 'r') as f:
                existing_results = json.load(f)
        except Exception as e:
            logger.error(f"Error loading existing results: {e}")
    
    # Merge results (avoid duplicates)
    existing_pr_numbers = {r['pr']['pr_number'] for r in existing_results}
    new_results = [r for r in results if r['pr']['pr_number'] not in existing_pr_numbers]
    
    all_results = existing_results + new_results
    
    # Save
    try:
        with open(linker.results_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        logger.info(f"Saved {len(all_results)} total PR-issue links")
    except Exception as e:
        logger.error(f"Error saving results: {e}")
    
    # Save seen PRs
    linker._save_seen_prs()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Backport PRs: Fetch historical PRs and link to issues'
    )
    parser.add_argument(
        '--prs',
        type=int,
        default=1000,
        help='Number of PRs to fetch (default: 1000, max: 10000)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Save progress every N PRs (default: 10)'
    )
    
    args = parser.parse_args()
    
    # Validate
    if args.prs > 10000:
        logger.warning("Maximum 10000 PRs allowed, setting to 10000")
        args.prs = 10000
    
    print(f"\n{'='*70}")
    print(f"PR Backport Tool")
    print(f"{'='*70}")
    print(f"Fetching: {args.prs} most recent PRs")
    print(f"Batch size: {args.batch_size}")
    print(f"{'='*70}\n")
    
    # Initialize components
    logger.info("Initializing components...")
    
    # GitHub monitor
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.warning("No GITHUB_TOKEN found in .env - rate limits will be lower")
    
    monitor = GitHubPRMonitor(github_token=github_token)
    
    # Issue pipeline
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
    
    logger.info(f"Loading issue pipeline (model: {embedding_model})...")
    pipeline = IssuePipeline(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    
    # PR vector store
    logger.info("Initializing PR vector store...")
    pr_vector_store = PRVectorStore(embedding_model=embedding_model)
    
    # PR-Issue linker
    linker = PRIssueLinker(
        pipeline=pipeline,
        github_monitor=monitor,
        pr_vector_store=pr_vector_store
    )
    
    logger.info(f"Currently tracking {len(linker.seen_prs)} PRs")
    logger.info(f"PR vector store has {pr_vector_store.count()} PRs")
    
    # Fetch PRs
    prs = fetch_prs_paginated(monitor, max_prs=args.prs)
    
    if not prs:
        logger.error("No PRs fetched!")
        return
    
    # Process PRs
    logger.info(f"\nProcessing {len(prs)} PRs...")
    results = process_pr_batch(
        prs=prs,
        linker=linker,
        monitor=monitor,
        pr_vector_store=pr_vector_store,
        batch_size=args.batch_size
    )
    
    # Final save
    logger.info("\nSaving final results...")
    save_results(results, linker)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Backport Complete!")
    print(f"{'='*70}")
    print(f"PRs fetched: {len(prs)}")
    print(f"PRs processed: {len(results)}")
    print(f"PRs skipped (already seen): {len(prs) - len(results)}")
    print(f"Total PRs tracked: {len(linker.seen_prs)}")
    print(f"PR vector store size: {pr_vector_store.count()}")
    print(f"\nResults saved to: {linker.results_file}")
    print(f"{'='*70}\n")
    
    print("Next steps:")
    print("1. View PR→Issue links:")
    print("   python3 pr_results_viewer.py")
    print("\n2. Generate Issue→PR links:")
    print("   python3 generate_issue_pr_links.py --issues 50")
    print("\n3. View Issue→PR links:")
    print("   python3 issue_pr_viewer.py")


if __name__ == '__main__':
    main()

# Made with Bob
