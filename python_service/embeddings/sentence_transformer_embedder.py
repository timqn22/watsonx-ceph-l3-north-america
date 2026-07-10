"""
Sentence Transformer Embedder
Uses open-source models - no API key required!
"""
import logging
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedder:
    """
    Generate embeddings using Sentence Transformers
    No API keys or external services required!
    """
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', cache_dir: str = './models'):
        """
        Initialize the embedder
        
        Args:
            model_name: Model to use. Options:
                - 'all-MiniLM-L6-v2': Fast, 384 dimensions (default)
                - 'all-mpnet-base-v2': Best quality, 768 dimensions
                - 'paraphrase-MiniLM-L6-v2': Good for paraphrase detection
            cache_dir: Directory to cache downloaded models
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        
        logger.info(f"Loading Sentence Transformer model: {model_name}")
        try:
            self.model = SentenceTransformer(model_name, cache_folder=cache_dir)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text
            
        Returns:
            Numpy array of embedding vector
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided, returning zero vector")
                return np.zeros(self.embedding_dim)
            
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return np.zeros(self.embedding_dim)
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 32, 
                          show_progress: bool = False) -> np.ndarray:
        """
        Generate embeddings for multiple texts (batch processing)
        
        Args:
            texts: List of input texts
            batch_size: Batch size for processing
            show_progress: Show progress bar
            
        Returns:
            Numpy array of shape (n_texts, embedding_dim)
        """
        try:
            if not texts:
                logger.warning("Empty text list provided")
                return np.array([])
            
            # Filter out empty texts and track indices
            valid_texts = []
            valid_indices = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_texts.append(text)
                    valid_indices.append(i)
            
            if not valid_texts:
                logger.warning("No valid texts after filtering")
                return np.zeros((len(texts), self.embedding_dim))
            
            # Generate embeddings for valid texts
            embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True
            )
            
            # Create result array with zeros for invalid texts
            result = np.zeros((len(texts), self.embedding_dim))
            for i, valid_idx in enumerate(valid_indices):
                result[valid_idx] = embeddings[i]
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return np.zeros((len(texts), self.embedding_dim))
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        return self.embedding_dim
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        return {
            'model_name': self.model_name,
            'embedding_dimension': self.embedding_dim,
            'cache_dir': self.cache_dir,
            'max_seq_length': self.model.max_seq_length
        }
    
    def __repr__(self) -> str:
        return f"SentenceTransformerEmbedder(model='{self.model_name}', dim={self.embedding_dim})"


# Convenience function for quick embedding generation
def generate_embedding(text: str, model_name: str = 'all-MiniLM-L6-v2') -> np.ndarray:
    """
    Quick function to generate a single embedding
    
    Args:
        text: Input text
        model_name: Model to use
        
    Returns:
        Embedding vector
    """
    embedder = SentenceTransformerEmbedder(model_name=model_name)
    return embedder.generate_embedding(text)


def generate_embeddings(texts: List[str], model_name: str = 'all-MiniLM-L6-v2', 
                       batch_size: int = 32) -> np.ndarray:
    """
    Quick function to generate multiple embeddings
    
    Args:
        texts: List of input texts
        model_name: Model to use
        batch_size: Batch size
        
    Returns:
        Array of embedding vectors
    """
    embedder = SentenceTransformerEmbedder(model_name=model_name)
    return embedder.generate_embeddings(texts, batch_size=batch_size)

# Made with Bob
