"""
Vector Store for Semantic Search
Uses ChromaDB with local sentence-transformers embeddings
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional, Tuple
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorStore:
    """Vector store for semantic search of Ceph issues"""
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "ceph_issues",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the vector store
        
        Args:
            persist_directory: Directory to persist the database
            collection_name: Name of the collection
            embedding_model: Name of the sentence-transformers model to use
                Options:
                - all-MiniLM-L6-v2: Fast, 384 dimensions (default)
                - all-mpnet-base-v2: Better quality, 768 dimensions
                - paraphrase-multilingual-MiniLM-L12-v2: Multilingual support
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        logger.info(f"Initializing ChromaDB at {persist_directory}")
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Load embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {collection_name}")
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a text string
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as list of floats
        """
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        embeddings = self.embedding_model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True
        )
        return embeddings.tolist()
    
    def add_issue(
        self,
        issue_id: str,
        text: str,
        metadata: Dict
    ) -> None:
        """
        Add a single issue to the vector store
        
        Args:
            issue_id: Unique identifier for the issue
            text: Text content to embed
            metadata: Metadata dictionary
        """
        embedding = self.embed_text(text)
        
        self.collection.add(
            ids=[str(issue_id)],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )
    
    def add_issues_batch(
        self,
        issue_ids: List[str],
        texts: List[str],
        metadatas: List[Dict]
    ) -> None:
        """
        Add multiple issues to the vector store in batch
        
        Args:
            issue_ids: List of unique identifiers
            texts: List of text contents to embed
            metadatas: List of metadata dictionaries
        """
        if not issue_ids or len(issue_ids) != len(texts) or len(issue_ids) != len(metadatas):
            raise ValueError("issue_ids, texts, and metadatas must have the same length")
        
        logger.info(f"Generating embeddings for {len(texts)} issues...")
        embeddings = self.embed_batch(texts)
        
        logger.info(f"Adding {len(issue_ids)} issues to vector store...")
        self.collection.add(
            ids=[str(id) for id in issue_ids],
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> Dict:
        """
        Search for similar issues
        
        Args:
            query: Search query text
            n_results: Number of results to return
            where: Optional metadata filter (e.g., {"status": "open"})
            where_document: Optional document content filter
        
        Returns:
            Dictionary with 'ids', 'distances', 'documents', 'metadatas'
        """
        query_embedding = self.embed_text(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document
        )
        
        return results
    
    def search_by_issue(
        self,
        issue_id: str,
        n_results: int = 10,
        where: Optional[Dict] = None
    ) -> Dict:
        """
        Find similar issues to a given issue
        
        Args:
            issue_id: ID of the issue to find similar issues for
            n_results: Number of results to return
            where: Optional metadata filter
        
        Returns:
            Dictionary with 'ids', 'distances', 'documents', 'metadatas'
        """
        # Get the issue's embedding
        result = self.collection.get(
            ids=[str(issue_id)],
            include=["embeddings"]
        )
        
        if not result['embeddings']:
            raise ValueError(f"Issue {issue_id} not found in vector store")
        
        embedding = result['embeddings'][0]
        
        # Search for similar issues
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results + 1,  # +1 because the issue itself will be included
            where=where
        )
        
        # Remove the original issue from results
        filtered_results = {
            'ids': [[]],
            'distances': [[]],
            'documents': [[]],
            'metadatas': [[]]
        }
        
        for i, id in enumerate(results['ids'][0]):
            if id != str(issue_id):
                filtered_results['ids'][0].append(id)
                filtered_results['distances'][0].append(results['distances'][0][i])
                filtered_results['documents'][0].append(results['documents'][0][i])
                filtered_results['metadatas'][0].append(results['metadatas'][0][i])
        
        # Limit to n_results
        for key in filtered_results:
            filtered_results[key][0] = filtered_results[key][0][:n_results]
        
        return filtered_results
    
    def get_issue(self, issue_id: str) -> Optional[Dict]:
        """
        Get a specific issue by ID
        
        Args:
            issue_id: Issue ID to retrieve
        
        Returns:
            Dictionary with issue data or None if not found
        """
        result = self.collection.get(
            ids=[str(issue_id)],
            include=["documents", "metadatas"]
        )
        
        if not result['ids']:
            return None
        
        return {
            'id': result['ids'][0],
            'document': result['documents'][0],
            'metadata': result['metadatas'][0]
        }
    
    def delete_issue(self, issue_id: str) -> None:
        """
        Delete an issue from the vector store
        
        Args:
            issue_id: Issue ID to delete
        """
        self.collection.delete(ids=[str(issue_id)])
    
    def count(self) -> int:
        """
        Get the total number of issues in the vector store
        
        Returns:
            Number of issues
        """
        return self.collection.count()
    
    def reset(self) -> None:
        """
        Delete all issues from the collection
        """
        logger.warning(f"Resetting collection: {self.collection_name}")
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the vector store
        
        Returns:
            Dictionary with statistics
        """
        count = self.count()
        
        stats = {
            'total_issues': count,
            'collection_name': self.collection_name,
            'persist_directory': self.persist_directory,
            'embedding_model': self.embedding_model_name,
            'embedding_dimension': self.embedding_model.get_sentence_embedding_dimension()
        }
        
        return stats
    
    def format_search_results(self, results: Dict) -> List[Dict]:
        """
        Format search results into a more readable structure
        
        Args:
            results: Raw search results from ChromaDB
        
        Returns:
            List of formatted result dictionaries
        """
        formatted = []
        
        if not results['ids'] or not results['ids'][0]:
            return formatted
        
        for i in range(len(results['ids'][0])):
            result = {
                'issue_id': results['ids'][0][i],
                'similarity_score': 1 - results['distances'][0][i],  # Convert distance to similarity
                'document': results['documents'][0][i] if results['documents'] else None,
                'metadata': results['metadatas'][0][i] if results['metadatas'] else {}
            }
            formatted.append(result)
        
        return formatted


if __name__ == "__main__":
    # Example usage
    store = VectorStore()
    
    print(f"Vector store stats: {store.get_stats()}")
    
    # Example: Add a test issue
    store.add_issue(
        issue_id="test_1",
        text="Subject: OSD crashes on startup\nDescription: The OSD daemon crashes immediately after starting with a segmentation fault.",
        metadata={
            'issue_id': 'test_1',
            'subject': 'OSD crashes on startup',
            'status': 'open',
            'priority': 'high'
        }
    )
    
    # Example: Search
    results = store.search("OSD crash problem", n_results=5)
    formatted = store.format_search_results(results)
    
    for result in formatted:
        print(f"\nIssue #{result['issue_id']} (similarity: {result['similarity_score']:.3f})")
        print(f"Subject: {result['metadata'].get('subject', 'N/A')}")

# Made with Bob
