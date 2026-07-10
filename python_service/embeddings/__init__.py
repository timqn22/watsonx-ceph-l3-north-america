"""
Embeddings package for Ceph Tracker Linker
Uses Sentence Transformers - no API keys required!
"""
from .sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
    generate_embedding,
    generate_embeddings
)

__all__ = [
    'SentenceTransformerEmbedder',
    'generate_embedding',
    'generate_embeddings'
]

# Made with Bob
