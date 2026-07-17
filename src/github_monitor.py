"""
GitHub PR Monitor for Ceph Repository
Monitors new PRs and finds similar Redmine issues
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from pathlib import Path
from .pr_vector_store import PRVectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitHubPRMonitor:
    """Monitor GitHub PRs and find similar Redmine issues"""
    
    def __init__(
        self,
        repo_owner: str = "ceph",
        repo_name: str = "ceph",
        github_token: Optional[str] = None
    ):
        """
        Initialize GitHub PR monitor
        
        Args:
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            github_token: Optional GitHub personal access token for higher rate limits
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"
        
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Ceph-Issue-Monitor'
        })
        
        if github_token:
            self.session.headers.update({
                'Authorization': f'token {github_token}'
            })
    
    def get_recent_prs(
        self,
        since_minutes: int = 15,
        state: str = 'open',
        max_prs: int = 100
    ) -> List[Dict]:
        """
        Get recent pull requests
        
        Args:
            since_minutes: Get PRs created in the last N minutes
            state: PR state ('open', 'closed', 'all')
            max_prs: Maximum number of PRs to fetch
        
        Returns:
            List of PR dictionaries
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        
        params = {
            'state': state,
            'sort': 'created',
            'direction': 'desc',
            'per_page': min(max_prs, 100)
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            all_prs = response.json()
            
            # Filter by time
            cutoff_time = datetime.utcnow() - timedelta(minutes=since_minutes)
            recent_prs = []
            
            for pr in all_prs:
                created_at = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                if created_at >= cutoff_time:
                    recent_prs.append(pr)
                else:
                    break  # PRs are sorted by creation time, so we can stop
            
            logger.info(f"Found {len(recent_prs)} PRs created in the last {since_minutes} minutes")
            return recent_prs
        
        except Exception as e:
            logger.error(f"Error fetching PRs: {e}")
            return []
    
    def get_pr_details(self, pr_number: int) -> Optional[Dict]:
        """
        Get detailed information about a specific PR
        
        Args:
            pr_number: PR number
        
        Returns:
            PR details dictionary
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        
        except Exception as e:
            logger.error(f"Error fetching PR #{pr_number}: {e}")
            return None
    
    def format_pr_for_search(self, pr: Dict) -> str:
        """
        Format PR data into searchable text
        
        Args:
            pr: PR dictionary from GitHub API
        
        Returns:
            Formatted text string
        """
        parts = []
        
        # Add title
        if 'title' in pr:
            parts.append(f"Title: {pr['title']}")
        
        # Add body/description
        if 'body' in pr and pr['body']:
            parts.append(f"Description: {pr['body']}")
        
        # Add labels
        if 'labels' in pr and pr['labels']:
            labels = [label['name'] for label in pr['labels']]
            parts.append(f"Labels: {', '.join(labels)}")
        
        return '\n'.join(parts)
    
    def extract_pr_metadata(self, pr: Dict) -> Dict:
        """
        Extract metadata from a PR
        
        Args:
            pr: PR dictionary from GitHub API
        
        Returns:
            Metadata dictionary
        """
        return {
            'pr_number': pr['number'],
            'title': pr['title'],
            'state': pr['state'],
            'author': pr['user']['login'],
            'created_at': pr['created_at'],
            'updated_at': pr['updated_at'],
            'url': pr['html_url'],
            'labels': [label['name'] for label in pr.get('labels', [])],
            'draft': pr.get('draft', False)
        }


class PRIssueLinker:
    """Link GitHub PRs to similar Redmine issues"""
    
    def __init__(self, pipeline, github_monitor: GitHubPRMonitor, pr_vector_store: Optional[PRVectorStore] = None):
        """
        Initialize PR-Issue linker
        
        Args:
            pipeline: IssuePipeline instance for searching issues
            github_monitor: GitHubPRMonitor instance
            pr_vector_store: Optional PRVectorStore for storing PRs
        """
        self.pipeline = pipeline
        self.github_monitor = github_monitor
        self.pr_vector_store = pr_vector_store
        self.results_file = Path("pr_issue_links.json")
        self.seen_prs_file = Path("seen_prs.json")
        
        # Load seen PRs
        self.seen_prs = self._load_seen_prs()
    
    def _load_seen_prs(self) -> set:
        """Load set of already processed PR numbers"""
        if self.seen_prs_file.exists():
            try:
                with open(self.seen_prs_file, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"Error loading seen PRs: {e}")
        return set()
    
    def _save_seen_prs(self):
        """Save set of processed PR numbers"""
        try:
            with open(self.seen_prs_file, 'w') as f:
                json.dump(list(self.seen_prs), f)
        except Exception as e:
            logger.error(f"Error saving seen PRs: {e}")
    
    def find_similar_issues(self, pr: Dict, n_results: int = 10) -> List[Dict]:
        """
        Find similar Redmine issues for a PR
        
        Args:
            pr: PR dictionary from GitHub API
            n_results: Number of similar issues to find
        
        Returns:
            List of similar issues
        """
        # Format PR for search
        search_text = self.github_monitor.format_pr_for_search(pr)
        
        # Search for similar issues
        results = self.pipeline.search_similar_issues(
            query=search_text,
            n_results=n_results
        )
        
        return results
    
    def initialize_with_recent_prs(self, max_prs: int = 10) -> List[Dict]:
        """
        Initialize by processing only the N most recent PRs (for first run)
        
        Args:
            max_prs: Maximum number of recent PRs to process
        
        Returns:
            List of PR-issue link dictionaries
        """
        logger.info(f"Initializing with {max_prs} most recent PRs...")
        
        # Get recent PRs (sorted by creation time, newest first)
        url = f"{self.github_monitor.base_url}/repos/{self.github_monitor.repo_owner}/{self.github_monitor.repo_name}/pulls"
        params = {
            'state': 'all',  # Get both open and closed
            'sort': 'created',
            'direction': 'desc',
            'per_page': max_prs
        }
        
        try:
            response = self.github_monitor.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            recent_prs = response.json()
        except Exception as e:
            logger.error(f"Error fetching recent PRs: {e}")
            return []
        
        new_links = []
        
        for pr in recent_prs:
            pr_number = pr['number']
            
            # Skip if already processed
            if pr_number in self.seen_prs:
                continue
            
            logger.info(f"Processing PR #{pr_number}: {pr['title']}")
            
            # Find similar issues
            similar_issues = self.find_similar_issues(pr, n_results=10)
            
            # Create link entry
            link_entry = {
                'pr': self.github_monitor.extract_pr_metadata(pr),
                'similar_issues': similar_issues,
                'processed_at': datetime.utcnow().isoformat(),
                'search_text': self.github_monitor.format_pr_for_search(pr)
            }
            
            new_links.append(link_entry)
            
            # Add PR to vector store if available
            if self.pr_vector_store:
                try:
                    self.pr_vector_store.add_pr(self.github_monitor.extract_pr_metadata(pr))
                except Exception as e:
                    logger.error(f"Error adding PR to vector store: {e}")
            
            # Mark as seen
            self.seen_prs.add(pr_number)
        
        # Save seen PRs
        if new_links:
            self._save_seen_prs()
            self._append_to_results(new_links)
        
        logger.info(f"Initialized with {len(new_links)} PRs")
        return new_links
    
    def process_new_prs(self, since_minutes: int = 15) -> List[Dict]:
        """
        Process new PRs and find similar issues
        
        Args:
            since_minutes: Check PRs from last N minutes
        
        Returns:
            List of PR-issue link dictionaries
        """
        # Get recent PRs
        recent_prs = self.github_monitor.get_recent_prs(since_minutes=since_minutes)
        
        new_links = []
        
        for pr in recent_prs:
            pr_number = pr['number']
            
            # Skip if already processed
            if pr_number in self.seen_prs:
                continue
            
            logger.info(f"Processing PR #{pr_number}: {pr['title']}")
            
            # Find similar issues
            similar_issues = self.find_similar_issues(pr, n_results=10)
            
            # Create link entry
            link_entry = {
                'pr': self.github_monitor.extract_pr_metadata(pr),
                'similar_issues': similar_issues,
                'processed_at': datetime.utcnow().isoformat(),
                'search_text': self.github_monitor.format_pr_for_search(pr)
            }
            
            new_links.append(link_entry)
            
            # Add PR to vector store if available
            if self.pr_vector_store:
                try:
                    self.pr_vector_store.add_pr(self.github_monitor.extract_pr_metadata(pr))
                except Exception as e:
                    logger.error(f"Error adding PR to vector store: {e}")
            
            # Mark as seen
            self.seen_prs.add(pr_number)
        
        # Save seen PRs
        if new_links:
            self._save_seen_prs()
            self._append_to_results(new_links)
        
        logger.info(f"Processed {len(new_links)} new PRs")
        return new_links
    
    def _append_to_results(self, new_links: List[Dict]):
        """Append new links to results file"""
        try:
            # Load existing results
            if self.results_file.exists():
                with open(self.results_file, 'r') as f:
                    existing_results = json.load(f)
            else:
                existing_results = []
            
            # Append new links
            existing_results.extend(new_links)
            
            # Save updated results
            with open(self.results_file, 'w') as f:
                json.dump(existing_results, f, indent=2)
            
            logger.info(f"Saved {len(new_links)} new PR-issue links to {self.results_file}")
        
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def get_all_links(self) -> List[Dict]:
        """Get all PR-issue links"""
        if self.results_file.exists():
            try:
                with open(self.results_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading results: {e}")
        return []
    
    def monitor_continuously(self, check_interval_minutes: int = 15):
        """
        Continuously monitor for new PRs
        
        Args:
            check_interval_minutes: Minutes between checks
        """
        logger.info(f"Starting continuous monitoring (checking every {check_interval_minutes} minutes)")
        
        while True:
            try:
                logger.info(f"Checking for new PRs at {datetime.now().isoformat()}")
                new_links = self.process_new_prs(since_minutes=check_interval_minutes + 5)
                
                if new_links:
                    logger.info(f"Found and processed {len(new_links)} new PRs")
                else:
                    logger.info("No new PRs found")
                
                # Wait for next check
                logger.info(f"Sleeping for {check_interval_minutes} minutes...")
                time.sleep(check_interval_minutes * 60)
            
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                logger.info("Continuing after error...")
                time.sleep(60)  # Wait 1 minute before retrying


if __name__ == "__main__":
    # Example usage
    from pipeline import IssuePipeline
    import os
    
    # Initialize pipeline
    pipeline = IssuePipeline(
        persist_directory=os.getenv('CHROMA_PERSIST_DIR', './chroma_db'),
        collection_name=os.getenv('COLLECTION_NAME', 'ceph_issues'),
        embedding_model=os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
    )
    
    # Initialize GitHub monitor
    github_token = os.getenv('GITHUB_TOKEN')  # Optional
    github_monitor = GitHubPRMonitor(github_token=github_token)
    
    # Initialize linker
    linker = PRIssueLinker(pipeline, github_monitor)
    
    # Process new PRs once
    links = linker.process_new_prs(since_minutes=60)
    print(f"Found {len(links)} new PRs")
    
    # Or monitor continuously
    # linker.monitor_continuously(check_interval_minutes=15)

# Made with Bob
