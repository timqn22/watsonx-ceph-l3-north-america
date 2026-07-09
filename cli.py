#!/usr/bin/env python3
"""
Command-line interface for Ceph Issue Semantic Search
"""

import click
import json
import os
from dotenv import load_dotenv
from src.pipeline import IssuePipeline
from src.vector_store import VectorStore
from src.redmine_scraper import RedmineScraper

# Load environment variables
load_dotenv()


@click.group()
def cli():
    """Ceph Issue Semantic Search - Scrape and search Ceph Redmine issues"""
    pass


@cli.command()
@click.option('--max-issues', type=int, default=None, help='Maximum number of issues to scrape (default: all)')
@click.option('--batch-size', type=int, default=100, help='Number of issues per batch (default: 100)')
@click.option('--delay', type=float, default=0.5, help='Delay between API requests in seconds (default: 0.5)')
@click.option('--no-save-raw', is_flag=True, help='Do not save raw JSON files')
@click.option('--status', default='*', help='Filter by status (* for all, "open", "closed", or ID)')
@click.option('--project', default=None, help='Filter by project ID or identifier')
def scrape(max_issues, batch_size, delay, no_save_raw, status, project):
    """Scrape issues from Ceph Redmine tracker and build the vector database"""
    
    click.echo("🔍 Starting Ceph issue scraping...")
    
    # Get configuration from environment
    redmine_url = os.getenv('REDMINE_URL', 'https://tracker.ceph.com')
    redmine_api_key = os.getenv('REDMINE_API_KEY')
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    # Initialize pipeline
    pipeline = IssuePipeline(
        redmine_url=redmine_url,
        redmine_api_key=redmine_api_key,
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    
    # Build filters
    filters = {'status_id': status}
    if project:
        filters['project_id'] = project
    
    # Run scraping
    stats = pipeline.scrape_and_index(
        max_issues=max_issues,
        batch_size=batch_size,
        delay=delay,
        save_raw=not no_save_raw,
        include=['journals'],
        **filters
    )
    
    click.echo("\n✅ Scraping complete!")
    click.echo(f"📊 Statistics:")
    click.echo(f"  - Total scraped: {stats['total_scraped']}")
    click.echo(f"  - Total indexed: {stats['total_indexed']}")
    click.echo(f"  - Errors: {stats['errors']}")
    click.echo(f"  - Vector store count: {stats['vector_store_count']}")


@cli.command()
@click.argument('query')
@click.option('--limit', '-n', type=int, default=10, help='Number of results to return (default: 10)')
@click.option('--status', default=None, help='Filter by status')
@click.option('--priority', default=None, help='Filter by priority')
@click.option('--json-output', is_flag=True, help='Output results as JSON')
def search(query, limit, status, priority, json_output):
    """Search for similar issues using semantic search"""
    
    # Get configuration from environment
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    # Initialize pipeline
    pipeline = IssuePipeline(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    
    # Build filters
    filters = {}
    if status:
        filters['status'] = status
    if priority:
        filters['priority'] = priority
    
    # Search
    results = pipeline.search_similar_issues(
        query=query,
        n_results=limit,
        filters=filters if filters else None
    )
    
    if json_output:
        click.echo(json.dumps(results, indent=2))
    else:
        click.echo(f"\n🔍 Search results for: '{query}'\n")
        
        if not results:
            click.echo("No results found.")
            return
        
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            click.echo(f"{i}. Issue #{metadata.get('issue_id', 'N/A')} "
                      f"(similarity: {result['similarity_score']:.3f})")
            click.echo(f"   Subject: {metadata.get('subject', 'N/A')}")
            click.echo(f"   Status: {metadata.get('status', 'N/A')} | "
                      f"Priority: {metadata.get('priority', 'N/A')}")
            click.echo(f"   URL: {metadata.get('url', 'N/A')}")
            click.echo()


@cli.command()
@click.argument('issue_id')
@click.option('--limit', '-n', type=int, default=10, help='Number of results to return (default: 10)')
@click.option('--json-output', is_flag=True, help='Output results as JSON')
def similar(issue_id, limit, json_output):
    """Find issues similar to a specific issue"""
    
    # Get configuration from environment
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    # Initialize pipeline
    pipeline = IssuePipeline(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    
    # Find similar issues
    try:
        results = pipeline.find_similar_to_issue(
            issue_id=issue_id,
            n_results=limit
        )
        
        if json_output:
            click.echo(json.dumps(results, indent=2))
        else:
            click.echo(f"\n🔍 Issues similar to #{issue_id}\n")
            
            if not results:
                click.echo("No similar issues found.")
                return
            
            for i, result in enumerate(results, 1):
                metadata = result['metadata']
                click.echo(f"{i}. Issue #{metadata.get('issue_id', 'N/A')} "
                          f"(similarity: {result['similarity_score']:.3f})")
                click.echo(f"   Subject: {metadata.get('subject', 'N/A')}")
                click.echo(f"   Status: {metadata.get('status', 'N/A')} | "
                          f"Priority: {metadata.get('priority', 'N/A')}")
                click.echo(f"   URL: {metadata.get('url', 'N/A')}")
                click.echo()
    
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)


@cli.command()
@click.argument('issue_id', type=int)
def update(issue_id):
    """Update a specific issue in the vector database"""
    
    # Get configuration from environment
    redmine_url = os.getenv('REDMINE_URL', 'https://tracker.ceph.com')
    redmine_api_key = os.getenv('REDMINE_API_KEY')
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    # Initialize pipeline
    pipeline = IssuePipeline(
        redmine_url=redmine_url,
        redmine_api_key=redmine_api_key,
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    
    click.echo(f"🔄 Updating issue #{issue_id}...")
    
    success = pipeline.update_issue(issue_id, include=['journals'])
    
    if success:
        click.echo(f"✅ Issue #{issue_id} updated successfully!")
    else:
        click.echo(f"❌ Failed to update issue #{issue_id}", err=True)


@cli.command()
@click.argument('issue_id', type=int)
@click.option('--include-journals', is_flag=True, help='Include issue journals/comments')
def fetch(issue_id, include_journals):
    """Fetch and display a specific issue from Redmine"""
    
    # Get configuration from environment
    redmine_url = os.getenv('REDMINE_URL', 'https://tracker.ceph.com')
    redmine_api_key = os.getenv('REDMINE_API_KEY')
    
    # Initialize scraper
    scraper = RedmineScraper(base_url=redmine_url, api_key=redmine_api_key)
    
    include = ['journals'] if include_journals else None
    issue = scraper.get_issue(issue_id, include=include)
    
    if not issue:
        click.echo(f"❌ Issue #{issue_id} not found", err=True)
        return
    
    click.echo(f"\n📋 Issue #{issue['id']}")
    click.echo(f"Subject: {issue.get('subject', 'N/A')}")
    click.echo(f"Status: {issue.get('status', {}).get('name', 'N/A')}")
    click.echo(f"Priority: {issue.get('priority', {}).get('name', 'N/A')}")
    click.echo(f"Author: {issue.get('author', {}).get('name', 'N/A')}")
    click.echo(f"Created: {issue.get('created_on', 'N/A')}")
    click.echo(f"Updated: {issue.get('updated_on', 'N/A')}")
    
    if 'description' in issue and issue['description']:
        click.echo(f"\nDescription:\n{issue['description']}")
    
    if include_journals and 'journals' in issue:
        click.echo(f"\n💬 Comments ({len(issue['journals'])}):")
        for journal in issue['journals']:
            if 'notes' in journal and journal['notes']:
                click.echo(f"\n  - {journal.get('user', {}).get('name', 'Unknown')} "
                          f"({journal.get('created_on', 'N/A')}):")
                click.echo(f"    {journal['notes']}")


@cli.command()
def stats():
    """Display statistics about the vector database"""
    
    # Get configuration from environment
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    # Initialize vector store
    store = VectorStore(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    
    stats = store.get_stats()
    
    click.echo("\n📊 Vector Database Statistics")
    click.echo(f"  - Total issues: {stats['total_issues']}")
    click.echo(f"  - Collection name: {stats['collection_name']}")
    click.echo(f"  - Persist directory: {stats['persist_directory']}")
    click.echo(f"  - Embedding model: {stats['embedding_model']}")
    click.echo(f"  - Embedding dimension: {stats['embedding_dimension']}")


@cli.command()
@click.confirmation_option(prompt='Are you sure you want to reset the database?')
def reset():
    """Reset the vector database (delete all issues)"""
    
    # Get configuration from environment
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    # Initialize vector store
    store = VectorStore(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    
    store.reset()
    click.echo("✅ Vector database reset successfully!")


if __name__ == '__main__':
    cli()

# Made with Bob
