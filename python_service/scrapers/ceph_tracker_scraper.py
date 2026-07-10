"""
Ceph Tracker Scraper
Fetches unlinked issues from Ceph tracker (tracker.ceph.com)
"""
import re
import logging
from typing import List, Dict, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class CephTrackerScraper:
    """Scraper for Ceph tracker issues"""
    
    def __init__(self, base_url: str = 'https://tracker.ceph.com', project_id: Optional[str] = None):
        """
        Initialize the scraper
        
        Args:
            base_url: Base URL for Ceph tracker
            project_id: Optional project identifier
        """
        self.base_url = base_url.rstrip('/')
        self.project_id = project_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CephTrackerLinker/1.0',
            'Accept': 'application/json'
        })
    
    def fetch_unlinked_trackers(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Fetch unlinked trackers (those without GitHub PR references)
        
        Args:
            limit: Maximum number of trackers to fetch
            offset: Offset for pagination
            
        Returns:
            List of tracker dictionaries
        """
        try:
            endpoint = f'{self.base_url}/issues.json'
            
            params = {
                'limit': limit,
                'offset': offset,
                'status_id': 'open',
                'sort': 'updated_on:desc'
            }
            
            if self.project_id:
                params['project_id'] = self.project_id
            
            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            issues = data.get('issues', [])
            
            # Filter for unlinked trackers
            unlinked = [issue for issue in issues if not self._has_github_link(issue)]
            
            # Transform to standardized format
            return [self._transform_tracker(issue) for issue in unlinked]
            
        except requests.RequestException as e:
            logger.error(f"Error fetching trackers: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return []
    
    def fetch_tracker(self, tracker_id: int) -> Optional[Dict]:
        """
        Fetch a specific tracker by ID
        
        Args:
            tracker_id: Tracker ID
            
        Returns:
            Tracker dictionary or None if not found
        """
        try:
            endpoint = f'{self.base_url}/issues/{tracker_id}.json'
            response = self.session.get(endpoint, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            issue = data.get('issue')
            
            if issue:
                return self._transform_tracker(issue)
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error fetching tracker {tracker_id}: {e}")
            return None
    
    def search_trackers(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search trackers by keyword
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching trackers
        """
        try:
            endpoint = f'{self.base_url}/issues.json'
            
            params = {
                'limit': limit,
                'status_id': 'open',
                'subject': f'~{query}'
            }
            
            if self.project_id:
                params['project_id'] = self.project_id
            
            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            issues = data.get('issues', [])
            
            # Filter for unlinked trackers
            unlinked = [issue for issue in issues if not self._has_github_link(issue)]
            
            return [self._transform_tracker(issue) for issue in unlinked]
            
        except requests.RequestException as e:
            logger.error(f"Error searching trackers: {e}")
            return []
    
    def _has_github_link(self, issue: Dict) -> bool:
        """
        Check if tracker has GitHub PR link
        
        Args:
            issue: Issue data from API
            
        Returns:
            True if has GitHub link
        """
        description = issue.get('description', '')
        
        # Check for GitHub PR URLs in description
        github_pr_pattern = r'github\.com/ceph/ceph/pull/\d+'
        if re.search(github_pr_pattern, description):
            return True
        
        # Check custom fields for GitHub links
        custom_fields = issue.get('custom_fields', [])
        for field in custom_fields:
            value = str(field.get('value', ''))
            if re.search(github_pr_pattern, value):
                return True
        
        return False
    
    def _transform_tracker(self, issue: Dict) -> Dict:
        """
        Transform tracker data to standardized format
        
        Args:
            issue: Raw issue data from API
            
        Returns:
            Standardized tracker dictionary
        """
        return {
            'id': issue.get('id'),
            'tracker_id': issue.get('id'),
            'subject': issue.get('subject', ''),
            'description': issue.get('description', ''),
            'status': issue.get('status', {}).get('name', ''),
            'priority': issue.get('priority', {}).get('name', ''),
            'author': issue.get('author', {}).get('name', ''),
            'created_on': issue.get('created_on', ''),
            'updated_on': issue.get('updated_on', ''),
            'project': issue.get('project', {}).get('name', ''),
            'tracker_type': issue.get('tracker', {}).get('name', ''),
            'url': f"{self.base_url}/issues/{issue.get('id')}",
            'combined_text': f"{issue.get('subject', '')} {issue.get('description', '')}".strip()
        }
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Made with Bob
