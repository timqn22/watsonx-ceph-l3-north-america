"""Switching embedder model re-embeds instead of keeping stale vectors."""

from __future__ import annotations

from app.models import Issue
from app.services.indexer import refresh_embeddings
from app.text import content_hash


class _StubEmbedder:
    def __init__(self, model_id, fill):
        self.model_id = model_id
        self.dimension = 4
        self._fill = fill

    def embed_texts(self, texts):
        return [[float(self._fill)] * 4 for _ in texts]


def test_changing_model_triggers_reembed(session):
    session.add(Issue(id=1, subject="rbd", description="mirror", is_open=True,
                      content_hash=content_hash("rbd", "mirror"), url="u"))
    session.commit()

    # First model embeds the row.
    a = _StubEmbedder("model-A", 1)
    assert refresh_embeddings(session, a) == 1
    row = session.get(Issue, 1)
    assert row.embedded_model == "model-A"
    assert row.embedding == [1.0, 1.0, 1.0, 1.0]

    # Same model again -> nothing to do (content + model unchanged).
    assert refresh_embeddings(session, a) == 0

    # Different model -> the row is re-embedded with the new vectors.
    b = _StubEmbedder("model-B", 9)
    assert refresh_embeddings(session, b) == 1
    row = session.get(Issue, 1)
    assert row.embedded_model == "model-B"
    assert row.embedding == [9.0, 9.0, 9.0, 9.0]
