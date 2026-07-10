"""
GitHub Pull Request Scraper
Fetches unlinked PRs from GitHub repository
"""
import re
import logging
from typing import List, Dict, Optional
from github import Github, GithubException
from datetime import datetime

logger = logging.getLogger(__name__)


class GithubPRScraper:
    """Scraper for GitHub pull requests"""
    
    def __init__(self, access_token: Optional[str] = None, repo: str = 'ceph/ceph'):
        """
        Initialize the scraper
        
        Args:
            access_token: GitHub personal access token (optional)
            repo: Repository in format 'owner/repo'
        """
        self.repo_name = repo
        
        # Initialize GitHub client
        # Skip empty or invalid tokens
        if access_token and access_token.strip() and not access_token.startswith('your_'):
            try:
                self.client = Github(access_token)
                logger.info("Using authenticated GitHub client")
            except Exception as e:
                logger.warning(f"Invalid token, falling back to unauthenticated: {e}")
                self.client = Github()
        else:
            # Unauthenticated client (rate limited to 60/hour)
            self.client = Github()
            logger.info("Using unauthenticated GitHub client (60 requests/hour)")
        
        try:
            self.repo = self.client.get_repo(repo)
            logger.info(f"Successfully connected to repository: {repo}")
        except GithubException as e:
            logger.error(f"Error accessing repository {repo}: {e}")
            raise
    
    def fetch_unlinked_prs(self, state: str = 'open', limit: int = 100) -> List[Dict]:
        """
        Fetch unlinked pull requests (those without tracker references)
        
        Args:
            state: PR state: 'open', 'closed', or 'all'
            limit: Maximum number of PRs to fetch
            
        Returns:
            List of PR dictionaries
        """
        try:
            pulls = self.repo.get_pulls(
                state=state,
                sort='updated',
                direction='desc'
            )
            
            unlinked_prs = []
            count = 0
            
            for pr in pulls:
                if count >= limit:
                    break
                
                # Check if PR has tracker link
                if not self._has_tracker_link(pr):
                    unlinked_prs.append(self._transform_pr(pr))
                    count += 1
            
            return unlinked_prs
            
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return []
    
    def fetch_pr(self, pr_number: int) -> Optional[Dict]:
        """
        Fetch a specific pull request by number
        
        Args:
            pr_number: Pull request number
            
        Returns:
            PR dictionary or None if not found
        """
        try:
            pr = self.repo.get_pull(pr_number)
            return self._transform_pr(pr)
            
        except GithubException as e:
            if e.status == 404:
                logger.error(f"PR #{pr_number} not found")
            else:
                logger.error(f"Error fetching PR #{pr_number}: {e}")
            return None
    
    def search_prs(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search pull requests by keyword
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching PRs
        """
        try:
            # GitHub search query format
            search_query = f'repo:{self.repo_name} is:pr {query}'
            
            results = self.client.search_issues(search_query)
            
            unlinked_prs = []
            count = 0
            
            for issue in results:
                if count >= limit:
                    break
                
                # Get full PR details
                pr = self.repo.get_pull(issue.number)
                
                if not self._has_tracker_link(pr):
                    unlinked_prs.append(self._transform_pr(pr))
                    count += 1
            
            return unlinked_prs
            
        except GithubException as e:
            logger.error(f"GitHub search error: {e}")
            return []
    
    def fetch_pr_files(self, pr_number: int) -> List[Dict]:
        """
        Get files changed in a PR
        
        Args:
            pr_number: Pull request number
            
        Returns:
            List of file change dictionaries
        """
        try:
            pr = self.repo.get_pull(pr_number)
            files = pr.get_files()
            
            return [
                {
                    'filename': f.filename,
                    'status': f.status,
                    'additions': f.additions,
                    'deletions': f.deletions,
                    'changes': f.changes,
                    'patch': f.patch if hasattr(f, 'patch') else None
                }
                for f in files
            ]
            
        except GithubException as e:
            logger.error(f"Error fetching PR files: {e}")
            return []
    
    def fetch_pr_commits(self, pr_number: int) -> List[Dict]:
        """
        Get commits in a PR
        
        Args:
            pr_number: Pull request number
            
        Returns:
            List of commit dictionaries
        """
        try:
            pr = self.repo.get_pull(pr_number)
            commits = pr.get_commits()
            
            return [
                {
                    'sha': c.sha,
                    'message': c.commit.message,
                    'author': c.commit.author.name,
                    'date': c.commit.author.date.isoformat() if c.commit.author.date else None
                }
                for c in commits
            ]
            
        except GithubException as e:
            logger.error(f"Error fetching PR commits: {e}")
            return []
    
    def get_rate_limit_status(self) -> Dict:
        """
        Check rate limit status
        
        Returns:
            Rate limit information dictionary
        """
        try:
            rate_limit = self.client.get_rate_limit()
            core = rate_limit.core
            
            return {
                'limit': core.limit,
                'remaining': core.remaining,
                'reset': core.reset.isoformat() if core.reset else None
            }
            
        except GithubException as e:
            logger.error(f"Error checking rate limit: {e}")
            return {'limit': 0, 'remaining': 0, 'reset': None}
    
    def _has_tracker_link(self, pr) -> bool:
        """
        Check if PR has tracker reference
        
        Args:
            pr: Pull request object
            
        Returns:
            True if has tracker link
        """
        title = pr.title or ''
        body = pr.body or ''
        
        # Patterns to detect tracker references
        tracker_patterns = [
            r'tracker\.ceph\.com/issues/\d+',
            r'\btracker[:\s]+#?\d+',
            r'\bissue[:\s]+#?\d+',
            r'\bfixes[:\s]+#?\d+'
        ]
        
        for pattern in tracker_patterns:
            if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, body, re.IGNORECASE):
                return True
        
        return False
    
    def _transform_pr(self, pr) -> Dict:
        """
        Transform PR data to standardized format
        
        Args:
            pr: Pull request object
            
        Returns:
            Standardized PR dictionary
        """
        return {
            'id': pr.id,
            'pr_number': pr.number,
            'title': pr.title,
            'body': pr.body or '',
            'state': pr.state,
            'author': pr.user.login if pr.user else '',
            'created_at': pr.created_at.isoformat() if pr.created_at else '',
            'updated_at': pr.updated_at.isoformat() if pr.updated_at else '',
            'merged_at': pr.merged_at.isoformat() if pr.merged_at else None,
            'labels': [label.name for label in pr.labels],
            'url': pr.html_url,
            'api_url': pr.url,
            'combined_text': f"{pr.title} {pr.body or ''}".strip(),
            'additions': pr.additions,
            'deletions': pr.deletions,
            'changed_files': pr.changed_files,
            'commits': pr.commits,
            'mergeable': pr.mergeable,
            'draft': pr.draft
        }
    
    def close(self):
        """Close the client connection"""
        # PyGithub doesn't require explicit closing
        pass
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Made with Bob
