"""Cross-encoder reranking.

A bi-encoder (embeddings) compares two *independent* vectors -- good recall,
limited precision. A cross-encoder reads the query and each candidate
*together* and scores their relevance directly -- much higher precision. It runs
locally on a small model (CPU-friendly), so it stays free and offline (no LLM
API, no watsonx). We only apply it to the on-demand top-K (issue-page related
PRs, recommendations), never the full batch job, so latency stays bounded.

Off by default (needs a one-time model download and adds a little latency).
Enable with RERANK_ENABLED=true. Uses sentence-transformers' CrossEncoder, which
is already a dependency; point RERANKER_MODEL at a Granite reranker if one that
runs locally is available, to stay IBM end-to-end.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from typing import Protocol

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    model_id: str
    enabled: bool

    def scores(self, query: str, docs: list[str]) -> list[float] | None:
        """Relevance in [0,1] for each doc vs the query; None if disabled."""
        ...


class NoopReranker:
    model_id = "disabled"
    enabled = False

    def scores(self, query: str, docs: list[str]) -> list[float] | None:
        return None


class CrossEncoderReranker:
    enabled = True

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder  # lazy import

        self._model = CrossEncoder(model_name)
        self.model_id = f"cross-encoder:{model_name}"

    def scores(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        raw = self._model.predict([(query, d) for d in docs])
        # ms-marco style models output a logit; squash to a 0..1 relevance.
        return [1.0 / (1.0 + math.exp(-float(x))) for x in raw]


def _build(settings: Settings) -> Reranker:
    if not settings.rerank_enabled:
        return NoopReranker()
    try:
        r = CrossEncoderReranker(settings.reranker_model)
        logger.info("Reranker enabled: %s", r.model_id)
        return r
    except Exception as exc:  # dep/model missing -> degrade to no reranking
        logger.warning("Reranker unavailable (%s); continuing without it", exc)
        return NoopReranker()


@lru_cache
def get_reranker() -> Reranker:
    return _build(get_settings())
