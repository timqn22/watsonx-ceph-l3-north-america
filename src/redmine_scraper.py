"""
Redmine Issue Scraper for Ceph Tracker
Fetches issues from tracker.ceph.com using the Redmine REST API
"""

import requests
import json
import time
from typing import Dict, List, Optional, Generator
from datetime import datetime
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedmineScraper:
    """Scraper for Ceph Redmine tracker issues"""
    
    def __init__(self, base_url: str = "https://tracker.ceph.com", api_key: Optional[str] = None):
        """
        Initialize the Redmine scraper
        
        Args:
            base_url: Base URL of the Redmine instance
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        # Set up authentication if API key is provided
        if self.api_key:
            self.session.headers.update({'X-Redmine-API-Key': self.api_key})
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get_issue(self, issue_id: int, include: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Fetch a single issue by ID
        
        Args:
            issue_id: The issue ID to fetch
            include: Optional list of associations to include (e.g., ['journals', 'attachments'])
        
        Returns:
            Issue data as dictionary or None if not found
        """
        url = f"{self.base_url}/issues/{issue_id}.json"
        params = {}
        
        if include:
            params['include'] = ','.join(include)
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get('issue')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Issue {issue_id} not found")
                return None
            elif e.response.status_code == 403:
                logger.error(f"Access forbidden for issue {issue_id}")
                return None
            else:
                logger.error(f"HTTP error fetching issue {issue_id}: {e}")
                return None
        except Exception as e:
            logger.error(f"Error fetching issue {issue_id}: {e}")
            return None
    
    def get_issues(
        self,
        project_id: Optional[str] = None,
        status_id: str = "*",
        limit: int = 100,
        offset: int = 0,
        include: Optional[List[str]] = None,
        **filters
    ) -> Dict:
        """
        Fetch multiple issues with pagination
        
        Args:
            project_id: Optional project identifier
            status_id: Status filter (* for all, 'open', 'closed', or specific ID)
            limit: Number of issues per page (max 100)
            offset: Offset for pagination
            include: Optional list of associations to include
            **filters: Additional filter parameters (tracker_id, priority_id, etc.)
        
        Returns:
            Dictionary with 'issues', 'total_count', 'limit', 'offset'
        """
        url = f"{self.base_url}/issues.json"
        params = {
            'limit': min(limit, 100),
            'offset': offset,
            'status_id': status_id
        }
        
        if project_id:
            params['project_id'] = project_id
        
        if include:
            params['include'] = ','.join(include)
        
        # Add any additional filters
        params.update(filters)
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching issues: {e}")
            return {'issues': [], 'total_count': 0, 'limit': limit, 'offset': offset}
    
    def scrape_all_issues(
        self,
        max_issues: Optional[int] = None,
        batch_size: int = 100,
        include: Optional[List[str]] = None,
        delay: float = 0.5,
        **filters
    ) -> Generator[Dict, None, None]:
        """
        Scrape all issues with pagination
        
        Args:
            max_issues: Maximum number of issues to fetch (None for all)
            batch_size: Number of issues per request (max 100)
            include: Optional list of associations to include
            delay: Delay between requests in seconds
            **filters: Additional filter parameters
        
        Yields:
            Individual issue dictionaries
        """
        offset = 0
        total_fetched = 0
        
        # First request to get total count
        first_batch = self.get_issues(
            limit=batch_size,
            offset=0,
            include=include,
            **filters
        )
        
        total_count = first_batch.get('total_count', 0)
        if max_issues:
            total_count = min(total_count, max_issues)
        
        logger.info(f"Total issues to fetch: {total_count}")
        
        # Process first batch
        for issue in first_batch.get('issues', []):
            yield issue
            total_fetched += 1
            if max_issues and total_fetched >= max_issues:
                return
        
        # Continue with remaining batches
        offset += batch_size
        
        with tqdm(total=total_count, initial=total_fetched, desc="Scraping issues") as pbar:
            while total_fetched < total_count:
                time.sleep(delay)  # Rate limiting
                
                batch = self.get_issues(
                    limit=batch_size,
                    offset=offset,
                    include=include,
                    **filters
                )
                
                issues = batch.get('issues', [])
                if not issues:
                    break
                
                for issue in issues:
                    yield issue
                    total_fetched += 1
                    pbar.update(1)
                    
                    if max_issues and total_fetched >= max_issues:
                        return
                
                offset += batch_size
    
    def get_projects(self, limit: int = 100) -> List[Dict]:
        """
        Fetch all projects
        
        Args:
            limit: Number of projects per page
        
        Returns:
            List of project dictionaries
        """
        url = f"{self.base_url}/projects.json"
        params = {'limit': limit}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get('projects', [])
        except Exception as e:
            logger.error(f"Error fetching projects: {e}")
            return []
    
    def get_trackers(self) -> List[Dict]:
        """
        Fetch all trackers (issue types)
        
        Returns:
            List of tracker dictionaries
        """
        url = f"{self.base_url}/trackers.json"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json().get('trackers', [])
        except Exception as e:
            logger.error(f"Error fetching trackers: {e}")
            return []
    
    def get_issue_statuses(self) -> List[Dict]:
        """
        Fetch all issue statuses
        
        Returns:
            List of status dictionaries
        """
        url = f"{self.base_url}/issue_statuses.json"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json().get('issue_statuses', [])
        except Exception as e:
            logger.error(f"Error fetching issue statuses: {e}")
            return []
    
    def format_issue_for_embedding(self, issue: Dict) -> str:
        """
        Format an issue into a text string suitable for embedding
        
        Args:
            issue: Issue dictionary from API
        
        Returns:
            Formatted text string
        """
        parts = []
        
        # Add subject
        if 'subject' in issue:
            parts.append(f"Subject: {issue['subject']}")
        
        # Add description
        if 'description' in issue and issue['description']:
            parts.append(f"Description: {issue['description']}")
        
        # Add tracker
        if 'tracker' in issue:
            parts.append(f"Type: {issue['tracker'].get('name', 'Unknown')}")
        
        # Add status
        if 'status' in issue:
            parts.append(f"Status: {issue['status'].get('name', 'Unknown')}")
        
        # Add priority
        if 'priority' in issue:
            parts.append(f"Priority: {issue['priority'].get('name', 'Unknown')}")
        
        # Add category
        if 'category' in issue:
            parts.append(f"Category: {issue['category'].get('name', 'Unknown')}")
        
        # Add custom fields
        if 'custom_fields' in issue:
            for field in issue['custom_fields']:
                name = field.get('name', '')
                value = field.get('value', '')
                if value:
                    if isinstance(value, list):
                        value = ', '.join(str(v) for v in value)
                    parts.append(f"{name}: {value}")
        
        # Add journals/comments (if available)
        if 'journals' in issue and issue['journals']:
            comments = []
            for journal in issue['journals']:
                # Only include journals with notes (comments)
                if 'notes' in journal and journal['notes']:
                    user = journal.get('user', {}).get('name', 'Unknown')
                    notes = journal['notes']
                    comments.append(f"{user}: {notes}")
            
            if comments:
                parts.append(f"Comments:\n" + "\n".join(comments))
        
        return '\n'.join(parts)
    
    def extract_issue_metadata(self, issue: Dict) -> Dict:
        """
        Extract metadata from an issue for storage
        
        Args:
            issue: Issue dictionary from API
        
        Returns:
            Metadata dictionary
        """
        metadata = {
            'issue_id': issue.get('id'),
            'subject': issue.get('subject', ''),
            'tracker': issue.get('tracker', {}).get('name', ''),
            'status': issue.get('status', {}).get('name', ''),
            'priority': issue.get('priority', {}).get('name', ''),
            'author': issue.get('author', {}).get('name', ''),
            'created_on': issue.get('created_on', ''),
            'updated_on': issue.get('updated_on', ''),
            'url': f"{self.base_url}/issues/{issue.get('id')}"
        }
        
        # Add project if available
        if 'project' in issue:
            metadata['project'] = issue['project'].get('name', '')
        
        # Add category if available
        if 'category' in issue:
            metadata['category'] = issue['category'].get('name', '')
        
        # Add assigned_to if available
        if 'assigned_to' in issue:
            metadata['assigned_to'] = issue['assigned_to'].get('name', '')
        
        return metadata


if __name__ == "__main__":
    # Example usage
    scraper = RedmineScraper()
    
    # Fetch a single issue
    issue = scraper.get_issue(45, include=['journals', 'attachments'])
    if issue:
        print(f"Issue #{issue['id']}: {issue['subject']}")
        print(f"Status: {issue['status']['name']}")
        print(f"\nFormatted for embedding:")
        print(scraper.format_issue_for_embedding(issue))

# Made with Bob
