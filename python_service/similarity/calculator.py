"""
Similarity Calculator
Calculates cosine similarity between embeddings
"""
import logging
from typing import List, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class SimilarityCalculator:
    """Calculate similarity between embeddings"""
    
    def __init__(self, threshold: float = 0.75):
        """
        Initialize calculator
        
        Args:
            threshold: Minimum similarity score to consider a match (0.0-1.0)
        """
        self.threshold = threshold
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0 and 1
        """
        try:
            # Reshape to 2D arrays if needed
            if embedding1.ndim == 1:
                embedding1 = embedding1.reshape(1, -1)
            if embedding2.ndim == 1:
                embedding2 = embedding2.reshape(1, -1)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(embedding1, embedding2)[0][0]
            
            # Ensure result is between 0 and 1
            return float(np.clip(similarity, 0.0, 1.0))
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def calculate_similarities(self, embedding: np.ndarray, 
                              embeddings: np.ndarray) -> np.ndarray:
        """
        Calculate similarity between one embedding and multiple embeddings
        
        Args:
            embedding: Single embedding vector
            embeddings: Array of embedding vectors (n_embeddings, embedding_dim)
            
        Returns:
            Array of similarity scores
        """
        try:
            # Reshape if needed
            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            
            # Calculate similarities
            similarities = cosine_similarity(embedding, embeddings)[0]
            
            # Ensure results are between 0 and 1
            return np.clip(similarities, 0.0, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating batch similarities: {e}")
            return np.zeros(len(embeddings))
    
    def find_top_matches(self, embedding: np.ndarray, embeddings: np.ndarray,
                        items: List[dict], top_k: int = 10) -> List[Tuple[dict, float]]:
        """
        Find top K most similar items
        
        Args:
            embedding: Query embedding
            embeddings: Array of candidate embeddings
            items: List of item dictionaries corresponding to embeddings
            top_k: Number of top matches to return
            
        Returns:
            List of (item, similarity_score) tuples, sorted by score descending
        """
        try:
            # Calculate all similarities
            similarities = self.calculate_similarities(embedding, embeddings)
            
            # Filter by threshold
            valid_indices = np.where(similarities >= self.threshold)[0]
            
            if len(valid_indices) == 0:
                logger.info("No matches found above threshold")
                return []
            
            # Get top K indices
            top_indices = valid_indices[np.argsort(similarities[valid_indices])[::-1][:top_k]]
            
            # Build result list
            results = [
                (items[idx], float(similarities[idx]))
                for idx in top_indices
            ]
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding top matches: {e}")
            return []
    
    def calculate_pairwise_similarities(self, embeddings1: np.ndarray,
                                       embeddings2: np.ndarray) -> np.ndarray:
        """
        Calculate pairwise similarities between two sets of embeddings
        
        Args:
            embeddings1: First set of embeddings (n1, dim)
            embeddings2: Second set of embeddings (n2, dim)
            
        Returns:
            Similarity matrix of shape (n1, n2)
        """
        try:
            similarities = cosine_similarity(embeddings1, embeddings2)
            return np.clip(similarities, 0.0, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating pairwise similarities: {e}")
            return np.zeros((len(embeddings1), len(embeddings2)))
    
    def get_confidence_level(self, similarity: float) -> str:
        """
        Get confidence level based on similarity score
        
        Args:
            similarity: Similarity score (0.0-1.0)
            
        Returns:
            Confidence level: 'very_high', 'high', 'medium', 'low'
        """
        if similarity >= 0.9:
            return 'very_high'
        elif similarity >= 0.8:
            return 'high'
        elif similarity >= 0.7:
            return 'medium'
        else:
            return 'low'
    
    def set_threshold(self, threshold: float):
        """Update similarity threshold"""
        if 0.0 <= threshold <= 1.0:
            self.threshold = threshold
        else:
            raise ValueError("Threshold must be between 0.0 and 1.0")
    
    def get_threshold(self) -> float:
        """Get current threshold"""
        return self.threshold


# Convenience functions
def calculate_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """Quick function to calculate similarity between two embeddings"""
    calculator = SimilarityCalculator()
    return calculator.calculate_similarity(embedding1, embedding2)


def find_similar_items(query_embedding: np.ndarray, candidate_embeddings: np.ndarray,
                      candidate_items: List[dict], threshold: float = 0.75,
                      top_k: int = 10) -> List[Tuple[dict, float]]:
    """Quick function to find similar items"""
    calculator = SimilarityCalculator(threshold=threshold)
    return calculator.find_top_matches(query_embedding, candidate_embeddings,
                                      candidate_items, top_k=top_k)

# Made with Bob
