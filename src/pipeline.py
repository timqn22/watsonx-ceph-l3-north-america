"""
Pipeline for scraping Ceph issues and building the vector database
"""

import os
import json
from typing import Optional, List, Dict
from datetime import datetime
from tqdm import tqdm
import logging

from .redmine_scraper import RedmineScraper
from .vector_store import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IssuePipeline:
    """Pipeline for scraping and indexing Ceph issues"""
    
    def __init__(
        self,
        redmine_url: str = "https://tracker.ceph.com",
        redmine_api_key: Optional[str] = None,
        persist_directory: str = "./chroma_db",
        collection_name: str = "ceph_issues",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the pipeline
        
        Args:
            redmine_url: URL of the Redmine instance
            redmine_api_key: Optional API key for authentication
            persist_directory: Directory to persist the vector database
            collection_name: Name of the collection
            embedding_model: Name of the sentence-transformers model
        """
        self.scraper = RedmineScraper(base_url=redmine_url, api_key=redmine_api_key)
        self.vector_store = VectorStore(
            persist_directory=persist_directory,
            collection_name=collection_name,
            embedding_model=embedding_model
        )
    
    def scrape_and_index(
        self,
        max_issues: Optional[int] = None,
        batch_size: int = 100,
        include: Optional[List[str]] = None,
        delay: float = 0.5,
        save_raw: bool = True,
        raw_data_dir: str = "./raw_issues",
        **filters
    ) -> Dict:
        """
        Scrape issues from Redmine and index them in the vector store
        
        Args:
            max_issues: Maximum number of issues to scrape (None for all)
            batch_size: Number of issues per API request
            include: Optional list of associations to include (e.g., ['journals'])
            delay: Delay between API requests in seconds
            save_raw: Whether to save raw JSON data
            raw_data_dir: Directory to save raw JSON files
            **filters: Additional filter parameters for the API
        
        Returns:
            Dictionary with statistics about the operation
        """
        stats = {
            'total_scraped': 0,
            'total_indexed': 0,
            'errors': 0,
            'start_time': datetime.now().isoformat()
        }
        
        # Create raw data directory if needed
        if save_raw:
            os.makedirs(raw_data_dir, exist_ok=True)
        
        # Prepare batches for vector store
        issue_ids_batch = []
        texts_batch = []
        metadatas_batch = []
        raw_issues_batch = []
        
        logger.info("Starting issue scraping and indexing...")
        
        try:
            for issue in self.scraper.scrape_all_issues(
                max_issues=max_issues,
                batch_size=batch_size,
                include=include,
                delay=delay,
                **filters
            ):
                stats['total_scraped'] += 1
                
                try:
                    # Format issue for embedding
                    text = self.scraper.format_issue_for_embedding(issue)
                    
                    # Extract metadata
                    metadata = self.scraper.extract_issue_metadata(issue)
                    
                    # Add to batch
                    issue_ids_batch.append(str(issue['id']))
                    texts_batch.append(text)
                    metadatas_batch.append(metadata)
                    raw_issues_batch.append(issue)
                    
                    # Process batch when it reaches batch_size
                    if len(issue_ids_batch) >= batch_size:
                        self._process_batch(
                            issue_ids_batch,
                            texts_batch,
                            metadatas_batch,
                            raw_issues_batch,
                            save_raw,
                            raw_data_dir,
                            stats
                        )
                        
                        # Clear batches
                        issue_ids_batch = []
                        texts_batch = []
                        metadatas_batch = []
                        raw_issues_batch = []
                
                except Exception as e:
                    logger.error(f"Error processing issue {issue.get('id', 'unknown')}: {e}")
                    stats['errors'] += 1
            
            # Process remaining issues in batch
            if issue_ids_batch:
                self._process_batch(
                    issue_ids_batch,
                    texts_batch,
                    metadatas_batch,
                    raw_issues_batch,
                    save_raw,
                    raw_data_dir,
                    stats
                )
        
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            stats['error_message'] = str(e)
        
        stats['end_time'] = datetime.now().isoformat()
        stats['vector_store_count'] = self.vector_store.count()
        
        logger.info(f"Scraping complete. Scraped: {stats['total_scraped']}, "
                   f"Indexed: {stats['total_indexed']}, Errors: {stats['errors']}")
        
        return stats
    
    def _process_batch(
        self,
        issue_ids: List[str],
        texts: List[str],
        metadatas: List[Dict],
        raw_issues: List[Dict],
        save_raw: bool,
        raw_data_dir: str,
        stats: Dict
    ) -> None:
        """
        Process a batch of issues
        
        Args:
            issue_ids: List of issue IDs
            texts: List of formatted texts
            metadatas: List of metadata dictionaries
            raw_issues: List of raw issue data
            save_raw: Whether to save raw JSON
            raw_data_dir: Directory for raw JSON files
            stats: Statistics dictionary to update
        """
        try:
            # Add to vector store
            self.vector_store.add_issues_batch(issue_ids, texts, metadatas)
            stats['total_indexed'] += len(issue_ids)
            
            # Save raw JSON if requested
            if save_raw:
                for issue in raw_issues:
                    issue_id = issue['id']
                    filepath = os.path.join(raw_data_dir, f"issue_{issue_id}.json")
                    with open(filepath, 'w') as f:
                        json.dump(issue, f, indent=2)
        
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            stats['errors'] += len(issue_ids)
    
    def update_issue(self, issue_id: int, include: Optional[List[str]] = None) -> bool:
        """
        Update a single issue in the vector store
        
        Args:
            issue_id: Issue ID to update
            include: Optional list of associations to include
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch latest issue data
            issue = self.scraper.get_issue(issue_id, include=include)
            
            if not issue:
                logger.warning(f"Issue {issue_id} not found")
                return False
            
            # Delete old version if exists
            try:
                self.vector_store.delete_issue(str(issue_id))
            except Exception:
                pass  # Issue might not exist yet
            
            # Format and add new version
            text = self.scraper.format_issue_for_embedding(issue)
            metadata = self.scraper.extract_issue_metadata(issue)
            
            self.vector_store.add_issue(str(issue_id), text, metadata)
            
            logger.info(f"Updated issue {issue_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating issue {issue_id}: {e}")
            return False
    
    def search_similar_issues(
        self,
        query: str,
        n_results: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar issues
        
        Args:
            query: Search query text
            n_results: Number of results to return
            filters: Optional metadata filters
        
        Returns:
            List of formatted search results
        """
        results = self.vector_store.search(
            query=query,
            n_results=n_results,
            where=filters
        )
        
        return self.vector_store.format_search_results(results)
    
    def find_similar_to_issue(
        self,
        issue_id: str,
        n_results: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Find issues similar to a given issue
        
        Args:
            issue_id: Issue ID to find similar issues for
            n_results: Number of results to return
            filters: Optional metadata filters
        
        Returns:
            List of formatted search results
        """
        results = self.vector_store.search_by_issue(
            issue_id=issue_id,
            n_results=n_results,
            where=filters
        )
        
        return self.vector_store.format_search_results(results)
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the pipeline
        
        Returns:
            Dictionary with statistics
        """
        return {
            'vector_store': self.vector_store.get_stats(),
            'redmine_url': self.scraper.base_url
        }
    
    def export_to_json(self, output_file: str, issue_ids: Optional[List[str]] = None) -> None:
        """
        Export issues to a JSON file
        
        Args:
            output_file: Path to output JSON file
            issue_ids: Optional list of specific issue IDs to export (None for all)
        """
        logger.info(f"Exporting issues to {output_file}")
        
        if issue_ids:
            issues = []
            for issue_id in issue_ids:
                issue = self.vector_store.get_issue(issue_id)
                if issue:
                    issues.append(issue)
        else:
            # Export all issues (this could be memory intensive for large collections)
            logger.warning("Exporting all issues - this may use significant memory")
            # Note: ChromaDB doesn't have a direct "get all" method, so we'd need to implement pagination
            # For now, we'll just export the metadata
            issues = []
        
        with open(output_file, 'w') as f:
            json.dump(issues, f, indent=2)
        
        logger.info(f"Exported {len(issues)} issues")


if __name__ == "__main__":
    # Example usage
    pipeline = IssuePipeline()
    
    # Scrape and index first 100 issues
    stats = pipeline.scrape_and_index(
        max_issues=100,
        batch_size=50,
        include=['journals'],
        delay=0.5
    )
    
    print(f"\nPipeline stats: {json.dumps(stats, indent=2)}")
    
    # Search for similar issues
    results = pipeline.search_similar_issues(
        query="OSD crash on startup",
        n_results=5
    )
    
    print("\nSearch results:")
    for result in results:
        print(f"\nIssue #{result['issue_id']} (similarity: {result['similarity_score']:.3f})")
        print(f"Subject: {result['metadata'].get('subject', 'N/A')}")
        print(f"Status: {result['metadata'].get('status', 'N/A')}")

# Made with Bob
