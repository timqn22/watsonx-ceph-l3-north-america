#!/usr/bin/env python3
"""
GitHub PR Monitor - Standalone Script
Monitors Ceph GitHub PRs and finds similar Redmine issues
"""

import os
import sys
from dotenv import load_dotenv
from src.pipeline import IssuePipeline
from src.github_monitor import GitHubPRMonitor, PRIssueLinker

# Load environment variables
load_dotenv()


def main():
    """Main function to run PR monitoring"""
    
    print("=" * 80)
    print("Ceph GitHub PR Monitor")
    print("=" * 80)
    print()
    
    # Get configuration
    persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    collection_name = os.getenv('COLLECTION_NAME', 'ceph_issues')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-en-v1.5')
    github_token = os.getenv('GITHUB_TOKEN')  # Optional
    
    print(f"📊 Loading issue database from: {persist_dir}")
    print(f"🤖 Using embedding model: {embedding_model}")
    
    if github_token:
        print("🔑 Using GitHub token (higher rate limits)")
    else:
        print("⚠️  No GitHub token - using anonymous access (lower rate limits)")
        print("   Set GITHUB_TOKEN in .env for better performance")
    
    print()
    
    # Initialize pipeline
    print("Loading pipeline...")
    pipeline = IssuePipeline(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model
    )
    print("✅ Pipeline loaded")
    print()
    
    # Initialize GitHub monitor
    github_monitor = GitHubPRMonitor(
        repo_owner="ceph",
        repo_name="ceph",
        github_token=github_token
    )
    
    # Initialize linker
    linker = PRIssueLinker(pipeline, github_monitor)
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "once":
            # Run once
            minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            print(f"🔍 Checking for PRs from the last {minutes} minutes...")
            print()
            
            links = linker.process_new_prs(since_minutes=minutes)
            
            if links:
                print(f"\n✅ Found {len(links)} new PRs with similar issues")
                print(f"📄 Results saved to: pr_issue_links.json")
                
                # Show summary
                for link in links:
                    pr = link['pr']
                    print(f"\nPR #{pr['pr_number']}: {pr['title']}")
                    print(f"   URL: {pr['url']}")
                    print(f"   Similar issues: {len(link['similar_issues'])}")
                    
                    # Show top 3 similar issues
                    for i, issue in enumerate(link['similar_issues'][:3], 1):
                        metadata = issue['metadata']
                        similarity = issue['similarity_score']
                        print(f"   {i}. Issue #{metadata['issue_id']} (similarity: {similarity:.3f})")
                        print(f"      {metadata['subject']}")
            else:
                print("ℹ️  No new PRs found")
        
        elif command == "continuous":
            # Run continuously
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 15
            print(f"🔄 Starting continuous monitoring (checking every {interval} minutes)")
            print("   Press Ctrl+C to stop")
            print()
            
            linker.monitor_continuously(check_interval_minutes=interval)
        
        elif command == "show":
            # Show all links
            links = linker.get_all_links()
            print(f"📊 Total PR-issue links: {len(links)}")
            print()
            
            for link in links[-10:]:  # Show last 10
                pr = link['pr']
                print(f"PR #{pr['pr_number']}: {pr['title']}")
                print(f"   Processed: {link['processed_at']}")
                print(f"   Similar issues: {len(link['similar_issues'])}")
                print()
        
        else:
            print(f"Unknown command: {command}")
            print_usage()
    
    else:
        # Default: run once for last 15 minutes
        print("🔍 Checking for PRs from the last 15 minutes...")
        print("   (Use 'python3 monitor_prs.py continuous' for continuous monitoring)")
        print()
        
        links = linker.process_new_prs(since_minutes=15)
        
        if links:
            print(f"\n✅ Found {len(links)} new PRs")
            print(f"📄 Results saved to: pr_issue_links.json")
        else:
            print("ℹ️  No new PRs found")


def print_usage():
    """Print usage information"""
    print("""
Usage:
    python3 monitor_prs.py [command] [options]

Commands:
    once [minutes]       Check for PRs once (default: last 60 minutes)
    continuous [minutes] Monitor continuously (default: check every 15 minutes)
    show                 Show all PR-issue links

Examples:
    python3 monitor_prs.py                    # Check last 15 minutes once
    python3 monitor_prs.py once 60            # Check last 60 minutes
    python3 monitor_prs.py continuous 15      # Monitor every 15 minutes
    python3 monitor_prs.py show               # Show all links

Output:
    Results are saved to pr_issue_links.json
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
