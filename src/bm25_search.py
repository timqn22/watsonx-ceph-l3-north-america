"""
BM25 search implementation for hybrid search
Combines keyword-based BM25 with semantic search
"""

import logging
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BM25Search:
    """BM25 keyword search for hybrid retrieval"""
    
    def __init__(self):
        """Initialize BM25 search"""
        self.bm25 = None
        self.documents = []
        self.doc_ids = []
        self.metadatas = []
        
    def index_documents(
        self,
        doc_ids: List[str],
        documents: List[str],
        metadatas: List[Dict]
    ) -> None:
        """
        Index documents for BM25 search
        
        Args:
            doc_ids: List of document IDs
            documents: List of document texts
            metadatas: List of metadata dictionaries
        """
        logger.info(f"Indexing {len(documents)} documents for BM25 search...")
        
        # Store documents and metadata
        self.doc_ids = doc_ids
        self.documents = documents
        self.metadatas = metadatas
        
        # Tokenize documents (simple whitespace tokenization)
        tokenized_docs = [doc.lower().split() for doc in documents]
        
        # Create BM25 index
        self.bm25 = BM25Okapi(tokenized_docs)
        
        logger.info("BM25 indexing complete")
    
    def search(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Dict]:
        """
        Search using BM25
        
        Args:
            query: Search query
            n_results: Number of results to return
        
        Returns:
            List of results with BM25 scores
        """
        if self.bm25 is None:
            logger.warning("BM25 index not initialized")
            return []
        
        # Tokenize query
        tokenized_query = query.lower().split()
        
        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top N indices
        top_indices = np.argsort(scores)[::-1][:n_results]
        
        # Format results
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include results with positive scores
                results.append({
                    'issue_id': self.doc_ids[idx],
                    'bm25_score': float(scores[idx]),
                    'document': self.documents[idx],
                    'metadata': self.metadatas[idx]
                })
        
        return results
    
    def get_score(self, query: str, doc_id: str) -> float:
        """
        Get BM25 score for a specific document
        
        Args:
            query: Search query
            doc_id: Document ID
        
        Returns:
            BM25 score
        """
        if self.bm25 is None or doc_id not in self.doc_ids:
            return 0.0
        
        # Find document index
        doc_idx = self.doc_ids.index(doc_id)
        
        # Tokenize query
        tokenized_query = query.lower().split()
        
        # Get score for this document
        scores = self.bm25.get_scores(tokenized_query)
        
        return float(scores[doc_idx])


class HybridSearch:
    """Hybrid search combining semantic and BM25 scores"""
    
    def __init__(
        self,
        semantic_weight: float = 0.9,
        bm25_weight: float = 0.1
    ):
        """
        Initialize hybrid search
        
        Args:
            semantic_weight: Weight for semantic similarity (default: 0.9)
            bm25_weight: Weight for BM25 score (default: 0.1)
        """
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.bm25_search = BM25Search()
        
        logger.info(f"Hybrid search initialized: semantic={semantic_weight}, bm25={bm25_weight}")
    
    def index_documents(
        self,
        doc_ids: List[str],
        documents: List[str],
        metadatas: List[Dict]
    ) -> None:
        """
        Index documents for BM25 search
        
        Args:
            doc_ids: List of document IDs
            documents: List of document texts
            metadatas: List of metadata dictionaries
        """
        self.bm25_search.index_documents(doc_ids, documents, metadatas)
    
    def combine_scores(
        self,
        semantic_results: List[Dict],
        query: str,
        n_results: int = 10
    ) -> List[Dict]:
        """
        Combine semantic and BM25 scores
        
        Args:
            semantic_results: Results from semantic search
            query: Original search query
            n_results: Number of results to return
        
        Returns:
            Combined results with hybrid scores
        """
        if not semantic_results:
            return []
        
        # Get BM25 scores for all semantic results
        bm25_results = self.bm25_search.search(query, n_results=len(semantic_results) * 2)
        
        # Create a map of doc_id to BM25 score
        bm25_scores = {r['issue_id']: r['bm25_score'] for r in bm25_results}
        
        # Normalize BM25 scores to [0, 1] range
        if bm25_scores:
            max_bm25 = max(bm25_scores.values())
            if max_bm25 > 0:
                bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}
        
        # Combine scores
        hybrid_results = []
        for result in semantic_results:
            doc_id = result['issue_id']
            semantic_score = result.get('similarity_score', 0.0)
            bm25_score = bm25_scores.get(doc_id, 0.0)
            
            # Calculate hybrid score
            hybrid_score = (
                self.semantic_weight * semantic_score +
                self.bm25_weight * bm25_score
            )
            
            # Create result with all scores
            hybrid_result = result.copy()
            hybrid_result['semantic_score'] = semantic_score
            hybrid_result['bm25_score'] = bm25_score
            hybrid_result['hybrid_score'] = hybrid_score
            hybrid_result['similarity_score'] = hybrid_score  # Update main score
            
            hybrid_results.append(hybrid_result)
        
        # Sort by hybrid score
        hybrid_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # Return top N
        return hybrid_results[:n_results]
    
    def update_weights(self, semantic_weight: float, bm25_weight: float) -> None:
        """
        Update the weights for hybrid search
        
        Args:
            semantic_weight: New weight for semantic similarity
            bm25_weight: New weight for BM25 score
        """
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        logger.info(f"Updated weights: semantic={semantic_weight}, bm25={bm25_weight}")


# Made with Bob