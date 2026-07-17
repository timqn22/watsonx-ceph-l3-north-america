"""
Vector store for GitHub Pull Requests
Stores PR embeddings for reverse search (find PRs similar to issues)
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PRVectorStore:
    """Vector store for GitHub PRs using ChromaDB"""
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db_prs",
        collection_name: str = "github_prs",
        embedding_model: str = "BAAI/bge-large-en-v1.5"
    ):
        """
        Initialize PR vector store
        
        Args:
            persist_directory: Directory to persist the database
            collection_name: Name of the collection
            embedding_model: Name of the sentence-transformers model
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        
        # Create persist directory if it doesn't exist
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing PR ChromaDB at {persist_directory}")
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Load embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Get embedding dimension
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.embedding_dim}")
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(
                name=collection_name,
            )
            logger.info(f"Loaded existing collection: {collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {collection_name}")
    
    def format_pr_for_embedding(self, pr: Dict) -> str:
        """
        Format PR data into text for embedding
        
        Args:
            pr: PR dictionary with metadata
        
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
            labels = pr['labels'] if isinstance(pr['labels'], list) else []
            if labels:
                parts.append(f"Labels: {', '.join(labels)}")
        
        return '\n'.join(parts)
    
    def add_pr(self, pr: Dict) -> bool:
        """
        Add a single PR to the vector store
        
        Args:
            pr: PR dictionary with metadata
        
        Returns:
            True if successful, False otherwise
        """
        try:
            pr_id = str(pr['pr_number'])
            
            # Check if PR already exists
            existing = self.collection.get(ids=[pr_id])
            if existing['ids']:
                logger.debug(f"PR #{pr_id} already exists, skipping")
                return False
            
            # Format PR for embedding
            pr_text = self.format_pr_for_embedding(pr)
            
            # Generate embedding
            embedding = self.embedding_model.encode(pr_text).tolist()
            
            # Prepare metadata
            metadata = {
                'pr_number': pr['pr_number'],
                'title': pr['title'],
                'state': pr.get('state', 'unknown'),
                'author': pr.get('author', 'unknown'),
                'created_at': pr.get('created_at', ''),
                'url': pr.get('url', ''),
                'labels': ','.join(pr.get('labels', [])) if pr.get('labels') else ''
            }
            
            # Add to collection
            self.collection.add(
                ids=[pr_id],
                embeddings=[embedding],
                documents=[pr_text],
                metadatas=[metadata]
            )
            
            logger.info(f"Added PR #{pr_id}: {pr['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding PR: {e}")
            return False
    
    def add_prs_batch(self, prs: List[Dict]) -> int:
        """
        Add multiple PRs to the vector store
        
        Args:
            prs: List of PR dictionaries
        
        Returns:
            Number of PRs added
        """
        added_count = 0
        for pr in prs:
            if self.add_pr(pr):
                added_count += 1
        
        logger.info(f"Added {added_count}/{len(prs)} PRs to vector store")
        return added_count
    
    def search_similar_prs(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Dict]:
        """
        Search for PRs similar to a query
        
        Args:
            query: Search query text
            n_results: Number of results to return
        
        Returns:
            List of similar PRs with metadata and similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            # Format results
            formatted_results = []
            if results['ids'] and results['ids'][0]:
                for i, pr_id in enumerate(results['ids'][0]):
                    result = {
                        'pr_number': int(pr_id),
                        'similarity_score': 1 - results['distances'][0][i],  # Convert distance to similarity
                        'metadata': results['metadatas'][0][i],
                        'document': results['documents'][0][i]
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching PRs: {e}")
            return []
    
    def get_pr(self, pr_number: int) -> Optional[Dict]:
        """
        Get a specific PR by number
        
        Args:
            pr_number: PR number
        
        Returns:
            PR data or None if not found
        """
        try:
            result = self.collection.get(ids=[str(pr_number)])
            if result['ids']:
                return {
                    'pr_number': pr_number,
                    'metadata': result['metadatas'][0],
                    'document': result['documents'][0]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting PR #{pr_number}: {e}")
            return None
    
    def count(self) -> int:
        """Get total number of PRs in the store"""
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Error counting PRs: {e}")
            return 0
    
    def get_stats(self) -> Dict:
        """Get statistics about the PR vector store"""
        return {
            'total_prs': self.count(),
            'collection_name': self.collection_name,
            'persist_directory': self.persist_directory,
            'embedding_model': self.embedding_model_name,
            'embedding_dimension': self.embedding_dim
        }

# Made with Bob
