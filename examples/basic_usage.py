#!/usr/bin/env python3
"""
Basic usage examples for Ceph Issue Semantic Search
"""

from src.pipeline import IssuePipeline
from src.redmine_scraper import RedmineScraper
from src.vector_store import VectorStore


def example_1_scrape_issues():
    """Example 1: Scrape issues from Ceph Redmine"""
    print("=" * 60)
    print("Example 1: Scraping Issues")
    print("=" * 60)
    
    pipeline = IssuePipeline(
        redmine_url="https://tracker.ceph.com",
        persist_directory="./example_db",
        embedding_model="all-MiniLM-L6-v2"
    )
    
    # Scrape first 100 issues
    stats = pipeline.scrape_and_index(
        max_issues=100,
        batch_size=50,
        delay=0.5,
        save_raw=False
    )
    
    print(f"\nScraped {stats['total_scraped']} issues")
    print(f"Indexed {stats['total_indexed']} issues")
    print(f"Errors: {stats['errors']}")


def example_2_search_issues():
    """Example 2: Search for similar issues"""
    print("\n" + "=" * 60)
    print("Example 2: Searching for Similar Issues")
    print("=" * 60)
    
    pipeline = IssuePipeline(
        persist_directory="./example_db",
        embedding_model="all-MiniLM-L6-v2"
    )
    
    # Search for issues related to OSD crashes
    query = "OSD crashes on startup with segmentation fault"
    results = pipeline.search_similar_issues(query, n_results=5)
    
    print(f"\nSearch query: '{query}'")
    print(f"Found {len(results)} similar issues:\n")
    
    for i, result in enumerate(results, 1):
        metadata = result['metadata']
        print(f"{i}. Issue #{metadata['issue_id']} (similarity: {result['similarity_score']:.3f})")
        print(f"   Subject: {metadata['subject']}")
        print(f"   Status: {metadata['status']} | Priority: {metadata['priority']}")
        print(f"   URL: {metadata['url']}\n")


def example_3_find_similar_to_issue():
    """Example 3: Find issues similar to a specific issue"""
    print("=" * 60)
    print("Example 3: Finding Similar Issues to a Specific Issue")
    print("=" * 60)
    
    pipeline = IssuePipeline(
        persist_directory="./example_db",
        embedding_model="all-MiniLM-L6-v2"
    )
    
    # Find issues similar to issue #45
    issue_id = "45"
    results = pipeline.find_similar_to_issue(issue_id, n_results=5)
    
    print(f"\nIssues similar to #{issue_id}:")
    print(f"Found {len(results)} similar issues:\n")
    
    for i, result in enumerate(results, 1):
        metadata = result['metadata']
        print(f"{i}. Issue #{metadata['issue_id']} (similarity: {result['similarity_score']:.3f})")
        print(f"   Subject: {metadata['subject']}")
        print(f"   Status: {metadata['status']}\n")


def example_4_fetch_single_issue():
    """Example 4: Fetch a single issue from Redmine"""
    print("=" * 60)
    print("Example 4: Fetching a Single Issue")
    print("=" * 60)
    
    scraper = RedmineScraper(base_url="https://tracker.ceph.com")
    
    # Fetch issue #45 with journals
    issue = scraper.get_issue(45, include=['journals'])
    
    if issue:
        print(f"\nIssue #{issue['id']}")
        print(f"Subject: {issue['subject']}")
        print(f"Status: {issue['status']['name']}")
        print(f"Priority: {issue['priority']['name']}")
        print(f"Created: {issue['created_on']}")
        
        if 'description' in issue and issue['description']:
            print(f"\nDescription:\n{issue['description'][:200]}...")
        
        if 'journals' in issue:
            print(f"\nComments: {len(issue['journals'])}")
    else:
        print("Issue not found")


def example_5_filtered_search():
    """Example 5: Search with metadata filters"""
    print("\n" + "=" * 60)
    print("Example 5: Filtered Search")
    print("=" * 60)
    
    pipeline = IssuePipeline(
        persist_directory="./example_db",
        embedding_model="all-MiniLM-L6-v2"
    )
    
    # Search only in open issues
    query = "performance degradation"
    results = pipeline.search_similar_issues(
        query,
        n_results=5,
        filters={"status": "open"}
    )
    
    print(f"\nSearch query: '{query}' (open issues only)")
    print(f"Found {len(results)} results:\n")
    
    for i, result in enumerate(results, 1):
        metadata = result['metadata']
        print(f"{i}. Issue #{metadata['issue_id']} - {metadata['subject']}")


def example_6_batch_operations():
    """Example 6: Batch operations with vector store"""
    print("\n" + "=" * 60)
    print("Example 6: Batch Operations")
    print("=" * 60)
    
    store = VectorStore(
        persist_directory="./example_db",
        embedding_model="all-MiniLM-L6-v2"
    )
    
    # Get statistics
    stats = store.get_stats()
    print(f"\nVector Store Statistics:")
    print(f"  Total issues: {stats['total_issues']}")
    print(f"  Embedding model: {stats['embedding_model']}")
    print(f"  Embedding dimension: {stats['embedding_dimension']}")
    
    # Example: Add multiple issues at once
    issue_ids = ["test_1", "test_2", "test_3"]
    texts = [
        "Subject: OSD crash\nDescription: OSD crashes on startup",
        "Subject: Monitor issue\nDescription: Monitor fails to start",
        "Subject: RGW problem\nDescription: RGW returns 500 errors"
    ]
    metadatas = [
        {"issue_id": "test_1", "subject": "OSD crash", "status": "open"},
        {"issue_id": "test_2", "subject": "Monitor issue", "status": "open"},
        {"issue_id": "test_3", "subject": "RGW problem", "status": "closed"}
    ]
    
    print("\nAdding 3 test issues in batch...")
    store.add_issues_batch(issue_ids, texts, metadatas)
    print("Done!")
    
    # Clean up test issues
    for issue_id in issue_ids:
        store.delete_issue(issue_id)
    print("Test issues cleaned up")


def example_7_update_issue():
    """Example 7: Update a specific issue"""
    print("\n" + "=" * 60)
    print("Example 7: Updating an Issue")
    print("=" * 60)
    
    pipeline = IssuePipeline(
        redmine_url="https://tracker.ceph.com",
        persist_directory="./example_db",
        embedding_model="all-MiniLM-L6-v2"
    )
    
    # Update issue #45
    issue_id = 45
    print(f"\nUpdating issue #{issue_id}...")
    
    success = pipeline.update_issue(issue_id, include=['journals'])
    
    if success:
        print(f"Issue #{issue_id} updated successfully!")
    else:
        print(f"Failed to update issue #{issue_id}")


def example_8_custom_scraping():
    """Example 8: Custom scraping with filters"""
    print("\n" + "=" * 60)
    print("Example 8: Custom Scraping with Filters")
    print("=" * 60)
    
    scraper = RedmineScraper(base_url="https://tracker.ceph.com")
    
    # Scrape only high priority open bugs
    print("\nScraping high priority open bugs...")
    
    count = 0
    for issue in scraper.scrape_all_issues(
        max_issues=10,
        batch_size=10,
        status_id='open',
        delay=0.5
    ):
        count += 1
        print(f"{count}. Issue #{issue['id']}: {issue['subject']}")
        print(f"   Priority: {issue['priority']['name']}")
        print(f"   Status: {issue['status']['name']}\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Ceph Issue Semantic Search - Usage Examples")
    print("=" * 60)
    
    # Run examples
    # Note: Comment out examples you don't want to run
    
    # example_1_scrape_issues()
    # example_2_search_issues()
    # example_3_find_similar_to_issue()
    example_4_fetch_single_issue()
    # example_5_filtered_search()
    # example_6_batch_operations()
    # example_7_update_issue()
    # example_8_custom_scraping()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)

# Made with Bob
