"""
Reranker for improving similarity search results
Uses cross-encoder models for more accurate relevance scoring
"""

import logging
from typing import List, Dict, Optional
from sentence_transformers import CrossEncoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Reranker:
    """Rerank search results using cross-encoder models"""
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: Optional[str] = None
    ):
        """
        Initialize reranker
        
        Args:
            model_name: Name of the cross-encoder model
                Popular options:
                - cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, good quality)
                - cross-encoder/ms-marco-MiniLM-L-12-v2 (slower, better quality)
                - BAAI/bge-reranker-base (high quality)
                - BAAI/bge-reranker-large (best quality, slower)
            device: Device to run on ('cpu', 'cuda', 'mps', or None for auto)
        """
        self.model_name = model_name
        logger.info(f"Loading reranker model: {model_name}")
        
        try:
            self.model = CrossEncoder(model_name, device=device)
            logger.info(f"Reranker loaded successfully on device: {self.model.device}")
        except Exception as e:
            logger.error(f"Error loading reranker: {e}")
            raise
    
    def rerank(
        self,
        query: str,
        results: List[Dict],
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Rerank search results using cross-encoder
        
        Args:
            query: The search query
            results: List of search results with 'text' or 'content' field
            top_k: Number of top results to return (None for all)
        
        Returns:
            Reranked list of results with updated similarity scores
        """
        if not results:
            return results
        
        # Extract texts from results
        texts = []
        for result in results:
            # Try different field names
            text = result.get('text') or result.get('content') or result.get('description', '')
            texts.append(text)
        
        # Create query-document pairs
        pairs = [[query, text] for text in texts]
        
        # Get reranking scores
        logger.info(f"Reranking {len(results)} results...")
        scores = self.model.predict(pairs)
        
        # Update results with new scores
        reranked_results = []
        for i, result in enumerate(results):
            result_copy = result.copy()
            result_copy['original_score'] = result.get('similarity_score', 0.0)
            result_copy['rerank_score'] = float(scores[i])
            result_copy['similarity_score'] = float(scores[i])  # Replace with rerank score
            reranked_results.append(result_copy)
        
        # Sort by rerank score
        reranked_results.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        # Return top_k if specified
        if top_k:
            reranked_results = reranked_results[:top_k]
        
        logger.info(f"Reranking complete. Top score: {reranked_results[0]['rerank_score']:.4f}")
        
        return reranked_results
    
    def rerank_with_threshold(
        self,
        query: str,
        results: List[Dict],
        threshold: float = 0.5,
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Rerank and filter results by threshold
        
        Args:
            query: The search query
            results: List of search results
            threshold: Minimum rerank score to include
            top_k: Maximum number of results to return
        
        Returns:
            Filtered and reranked results
        """
        reranked = self.rerank(query, results, top_k=None)
        
        # Filter by threshold
        filtered = [r for r in reranked if r['rerank_score'] >= threshold]
        
        # Apply top_k if specified
        if top_k:
            filtered = filtered[:top_k]
        
        logger.info(f"Filtered to {len(filtered)} results above threshold {threshold}")
        
        return filtered


class RerankerPipeline:
    """Pipeline wrapper that adds reranking to search results"""
    
    def __init__(
        self,
        base_pipeline,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        enable_reranking: bool = True,
        device: Optional[str] = None
    ):
        """
        Initialize reranker pipeline
        
        Args:
            base_pipeline: The base IssuePipeline instance
            reranker_model: Name of the reranker model
            enable_reranking: Whether to enable reranking by default
            device: Device to run reranker on
        """
        self.base_pipeline = base_pipeline
        self.enable_reranking = enable_reranking
        
        if enable_reranking:
            self.reranker = Reranker(model_name=reranker_model, device=device)
        else:
            self.reranker = None
    
    def search_similar_issues(
        self,
        query: str,
        n_results: int = 10,
        filters: Optional[Dict] = None,
        use_reranker: Optional[bool] = None,
        rerank_top_k: Optional[int] = None,
        rerank_threshold: Optional[float] = None
    ) -> List[Dict]:
        """
        Search with optional reranking
        
        Args:
            query: Search query
            n_results: Number of initial results to fetch
            filters: Metadata filters
            use_reranker: Override default reranking setting
            rerank_top_k: Number of results after reranking
            rerank_threshold: Minimum rerank score
        
        Returns:
            Search results (reranked if enabled)
        """
        # Get initial results (fetch more for reranking)
        fetch_count = n_results * 3 if self.enable_reranking else n_results
        results = self.base_pipeline.search_similar_issues(
            query=query,
            n_results=fetch_count,
            filters=filters
        )
        
        # Apply reranking if enabled
        should_rerank = use_reranker if use_reranker is not None else self.enable_reranking
        
        if should_rerank and self.reranker and results:
            if rerank_threshold is not None:
                results = self.reranker.rerank_with_threshold(
                    query=query,
                    results=results,
                    threshold=rerank_threshold,
                    top_k=rerank_top_k or n_results
                )
            else:
                results = self.reranker.rerank(
                    query=query,
                    results=results,
                    top_k=rerank_top_k or n_results
                )
        else:
            # Just limit to n_results
            results = results[:n_results]
        
        return results
    
    def find_similar_to_issue(
        self,
        issue_id: str,
        n_results: int = 10,
        filters: Optional[Dict] = None,
        use_reranker: Optional[bool] = None,
        rerank_top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Find similar issues with optional reranking
        
        Args:
            issue_id: Issue ID to find similar issues for
            n_results: Number of results
            filters: Metadata filters
            use_reranker: Override default reranking setting
            rerank_top_k: Number of results after reranking
        
        Returns:
            Similar issues (reranked if enabled)
        """
        # Get initial results
        fetch_count = n_results * 3 if self.enable_reranking else n_results
        results = self.base_pipeline.find_similar_to_issue(
            issue_id=issue_id,
            n_results=fetch_count,
            filters=filters
        )
        
        # For issue-to-issue similarity, we need the source issue text
        # Get the source issue
        try:
            source_results = self.base_pipeline.vector_store.collection.get(
                ids=[issue_id],
                include=['documents']
            )
            if source_results and source_results['documents']:
                query = source_results['documents'][0]
            else:
                logger.warning(f"Could not find source issue {issue_id} for reranking")
                return results[:n_results]
        except Exception as e:
            logger.error(f"Error getting source issue: {e}")
            return results[:n_results]
        
        # Apply reranking if enabled
        should_rerank = use_reranker if use_reranker is not None else self.enable_reranking
        
        if should_rerank and self.reranker and results:
            results = self.reranker.rerank(
                query=query,
                results=results,
                top_k=rerank_top_k or n_results
            )
        else:
            results = results[:n_results]
        
        return results

# Made with Bob
