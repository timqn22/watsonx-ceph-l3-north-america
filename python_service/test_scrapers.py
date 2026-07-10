#!/usr/bin/env python3
"""
Test script for scrapers
Usage: python test_scrapers.py
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers import CephTrackerScraper, GithubPRScraper

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title=""):
    """Print a separator line"""
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)
    print()


def test_ceph_tracker_scraper():
    """Test Ceph tracker scraper"""
    print_separator("Testing Ceph Tracker Scraper")
    
    try:
        base_url = os.getenv('CEPH_TRACKER_URL', 'https://tracker.ceph.com')
        
        with CephTrackerScraper(base_url=base_url) as scraper:
            print(f"Fetching unlinked trackers (limit: 5)...")
            trackers = scraper.fetch_unlinked_trackers(limit=5)
            
            if not trackers:
                print("⚠️  No unlinked trackers found (or API error)")
            else:
                print(f"✓ Found {len(trackers)} unlinked tracker(s)\n")
                
                for idx, tracker in enumerate(trackers, 1):
                    print(f"Tracker #{idx}:")
                    print(f"  ID: {tracker['tracker_id']}")
                    print(f"  Subject: {tracker['subject']}")
                    print(f"  Status: {tracker['status']}")
                    print(f"  Priority: {tracker['priority']}")
                    print(f"  URL: {tracker['url']}")
                    print(f"  Text length: {len(tracker['combined_text'])} chars")
                    print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Ceph tracker scraper: {e}")
        logger.exception("Ceph tracker scraper error")
        return False


def test_github_pr_scraper():
    """Test GitHub PR scraper"""
    print_separator("Testing GitHub PR Scraper")
    
    try:
        github_token = os.getenv('GITHUB_TOKEN')
        repo = os.getenv('GITHUB_REPO', 'ceph/ceph')
        
        with GithubPRScraper(access_token=github_token, repo=repo) as scraper:
            # Check rate limit first
            rate_limit = scraper.get_rate_limit_status()
            print("GitHub API Rate Limit:")
            print(f"  Limit: {rate_limit['limit']}")
            print(f"  Remaining: {rate_limit['remaining']}")
            print(f"  Resets at: {rate_limit['reset']}")
            print()
            
            if rate_limit['remaining'] > 0:
                print(f"Fetching unlinked PRs (limit: 5)...")
                prs = scraper.fetch_unlinked_prs(limit=5)
                
                if not prs:
                    print("⚠️  No unlinked PRs found")
                else:
                    print(f"✓ Found {len(prs)} unlinked PR(s)\n")
                    
                    for idx, pr in enumerate(prs, 1):
                        print(f"PR #{idx}:")
                        print(f"  Number: #{pr['pr_number']}")
                        print(f"  Title: {pr['title']}")
                        print(f"  State: {pr['state']}")
                        print(f"  Author: {pr['author']}")
                        print(f"  URL: {pr['url']}")
                        print(f"  Text length: {len(pr['combined_text'])} chars")
                        print(f"  Files changed: {pr['changed_files']}")
                        print()
            else:
                print("⚠️  GitHub API rate limit exceeded. Please wait or provide a token.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing GitHub PR scraper: {e}")
        logger.exception("GitHub PR scraper error")
        return False


def main():
    """Main test function"""
    print_separator("Ceph Tracker Linker - Python Scraper Test")
    
    # Test Ceph tracker scraper
    ceph_success = test_ceph_tracker_scraper()
    
    # Test GitHub PR scraper
    github_success = test_github_pr_scraper()
    
    # Summary
    print_separator("Test Summary")
    print(f"Ceph Tracker Scraper: {'✓ PASS' if ceph_success else '✗ FAIL'}")
    print(f"GitHub PR Scraper: {'✓ PASS' if github_success else '✗ FAIL'}")
    print()
    
    if ceph_success and github_success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed. Check the output above for details.")
    
    print()
    print("To run with authentication:")
    print("  GITHUB_TOKEN=your_token python test_scrapers.py")
    print()
    print("To run unit tests:")
    print("  pytest tests/")
    print_separator()
    
    return 0 if (ceph_success and github_success) else 1


if __name__ == '__main__':
    sys.exit(main())

# Made with Bob
