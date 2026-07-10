"""Embedding backends.

The whole app depends only on the :class:`Embedder` protocol, so the storage
and matching layers never know which model produced a vector. Three backends:

  * WatsonxGraniteEmbedder -- real IBM Granite embeddings via ibm-watsonx-ai.
      This is the intended production/demo backend for the watsonx challenge.
  * LocalEmbedder          -- sentence-transformers, runs offline, no creds.
  * HashEmbedder           -- deterministic feature-hashing, numpy only.
      Zero dependencies beyond numpy, so tests and a first-boot demo work with
      nothing installed and no network. It captures lexical overlap, which is
      enough to prove the linkage pipeline end-to-end.

``get_embedder`` auto-selects: watsonx if configured, else local if installed,
else hash. Force a choice with EMBEDDER_BACKEND.
"""

from __future__ import annotations

import hashlib
import logging
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    """Anything that turns text into fixed-length unit vectors."""

    model_id: str
    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _CachingMixin:
    """Adds a per-process cache so identical text is embedded once per run."""

    model_id: str

    def _embed_impl(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError

    def __init__(self) -> None:
        self._cache: dict[str, list[float]] = {}

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in texts if _cache_key(t) not in self._cache]
        # De-duplicate before hitting the model.
        for t, vec in zip(
            dict.fromkeys(missing), self._embed_impl(list(dict.fromkeys(missing)))
        ):
            self._cache[_cache_key(t)] = vec
        return [self._cache[_cache_key(t)] for t in texts]


class HashEmbedder(_CachingMixin):
    """Deterministic feature-hashing embedder (the "always works" fallback).

    Uses the hashing trick with tf weighting, then L2-normalizes so cosine
    similarity is meaningful. Not semantic, but captures shared vocabulary --
    plenty to demonstrate the linkage flow before Granite is wired up.
    """

    model_id = "hash-embedder-v1"

    def __init__(self, dimension: int = 512) -> None:
        super().__init__()
        self.dimension = dimension

    def _embed_impl(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = np.zeros(self.dimension, dtype=np.float32)
            for tok in _TOKEN_RE.findall(text.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % self.dimension] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            out.append(vec.tolist())
        return out


class LocalEmbedder(_CachingMixin):
    """sentence-transformers backend for offline dev without watsonx creds."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        super().__init__()
        from sentence_transformers import SentenceTransformer  # lazy import

        self._model = SentenceTransformer(model_name)
        self.model_id = f"local:{model_name}"
        self.dimension = self._model.get_sentence_embedding_dimension()

    def _embed_impl(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        arr = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return arr.tolist()


class WatsonxGraniteEmbedder(_CachingMixin):
    """Real IBM Granite embeddings through the ibm-watsonx-ai SDK.

    Batches to the model's input cap and returns unit vectors. Requires
    WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL and a Granite embed model id.
    """

    def __init__(self, settings: Settings, batch_size: int = 96) -> None:
        super().__init__()
        from ibm_watsonx_ai import Credentials  # lazy import
        from ibm_watsonx_ai.foundation_models import Embeddings

        self._embeddings = Embeddings(
            model_id=settings.watsonx_embed_model_id,
            credentials=Credentials(
                url=settings.watsonx_url, api_key=settings.watsonx_api_key
            ),
            project_id=settings.watsonx_project_id,
        )
        self.model_id = f"watsonx:{settings.watsonx_embed_model_id}"
        self._batch_size = batch_size
        self.dimension = 0  # discovered on first call

    def _embed_impl(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            vectors.extend(self._embeddings.embed_documents(texts=batch))
        if vectors and not self.dimension:
            self.dimension = len(vectors[0])
        # Normalize so cosine == dot product downstream.
        normed: list[list[float]] = []
        for v in vectors:
            a = np.asarray(v, dtype=np.float32)
            n = np.linalg.norm(a)
            normed.append((a / n).tolist() if n > 0 else a.tolist())
        return normed


def _build_embedder(settings: Settings) -> Embedder:
    choice = settings.embedder_backend.lower()

    if choice == "hash":
        return HashEmbedder()
    if choice == "local":
        return LocalEmbedder()
    if choice == "watsonx":
        return WatsonxGraniteEmbedder(settings)

    # auto
    if settings.watsonx_configured:
        try:
            emb = WatsonxGraniteEmbedder(settings)
            logger.info("Using watsonx Granite embedder: %s", emb.model_id)
            return emb
        except Exception as exc:  # SDK missing or bad creds -> degrade gracefully
            logger.warning("watsonx embedder unavailable (%s); falling back", exc)
    try:
        emb = LocalEmbedder()
        logger.info("Using local embedder: %s", emb.model_id)
        return emb
    except Exception as exc:
        logger.warning("local embedder unavailable (%s); using hash fallback", exc)
    logger.info("Using hash embedder (deterministic fallback)")
    return HashEmbedder()


@lru_cache
def get_embedder() -> Embedder:
    """Return a cached process-wide embedder chosen from settings."""
    return _build_embedder(get_settings())
