"""Tests for the hybrid retrieval engine — metadata-first, semantic-second."""

from __future__ import annotations

import numpy as np
import pytest

from membrane.models import MemoryRecord
from membrane.retrieval import EmbeddingEngine, cosine_similarity, semantic_rerank


def test_cosine_similarity_identical():
    """Identical vectors should have similarity 1.0."""
    v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    """Orthogonal vectors should have similarity 0.0."""
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_zero_vector():
    """A zero vector should return 0.0 similarity."""
    a = np.array([1.0, 2.0], dtype=np.float32)
    b = np.array([0.0, 0.0], dtype=np.float32)
    assert cosine_similarity(a, b) == 0.0


def test_semantic_rerank_ranking():
    """Memories closer to the query should rank higher."""
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    mem_close = MemoryRecord(
        memory_id="close",
        namespace="test",
        walrus_blob_id="blob1",
        content_hash="hash1",
        timestamp="2024-01-01",
        embedding=[0.9, 0.1, 0.0],
    )
    mem_far = MemoryRecord(
        memory_id="far",
        namespace="test",
        walrus_blob_id="blob2",
        content_hash="hash2",
        timestamp="2024-01-01",
        embedding=[0.0, 0.0, 1.0],
    )
    mem_mid = MemoryRecord(
        memory_id="mid",
        namespace="test",
        walrus_blob_id="blob3",
        content_hash="hash3",
        timestamp="2024-01-01",
        embedding=[0.5, 0.5, 0.0],
    )

    results = semantic_rerank(query, [mem_far, mem_close, mem_mid], limit=3)
    ids = [r[0].memory_id for r in results]
    assert ids[0] == "close"
    assert ids[-1] == "far"


def test_semantic_rerank_limit():
    """Limit should cap the number of returned results."""
    query = np.array([1.0, 0.0], dtype=np.float32)
    mems = [
        MemoryRecord(
            memory_id=f"m{i}",
            namespace="test",
            walrus_blob_id=f"blob{i}",
            content_hash=f"hash{i}",
            timestamp="2024-01-01",
            embedding=[float(i), 0.0],
        )
        for i in range(10)
    ]
    results = semantic_rerank(query, mems, limit=3)
    assert len(results) == 3


def test_semantic_rerank_skips_no_embedding():
    """Memories without embeddings are placed at the end."""
    query = np.array([1.0, 0.0], dtype=np.float32)
    mem_no_emb = MemoryRecord(
        memory_id="no_emb",
        namespace="test",
        walrus_blob_id="blob1",
        content_hash="hash1",
        timestamp="2024-01-01",
        embedding=None,
    )
    mem_with = MemoryRecord(
        memory_id="with",
        namespace="test",
        walrus_blob_id="blob2",
        content_hash="hash2",
        timestamp="2024-01-01",
        embedding=[1.0, 0.0],
    )

    results = semantic_rerank(query, [mem_no_emb, mem_with], limit=5)
    assert len(results) == 2
    assert results[0][0].memory_id == "with"
    assert results[0][1] > 0  # Scored
    assert results[1][0].memory_id == "no_emb"
    assert results[1][1] == 0.0  # Unscored


@pytest.mark.slow
def test_embedding_engine_encode():
    """Integration test: EmbeddingEngine should produce a 384-dim vector.

    This test downloads the model on first run (~22 MB).
    Mark it as slow so it can be skipped in CI with -m 'not slow'.
    """
    engine = EmbeddingEngine("all-MiniLM-L6-v2")
    vec = engine.encode("Hello world")
    assert vec.shape == (384,)
    assert vec.dtype == np.float32
