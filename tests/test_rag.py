import pytest

def test_retrieve_top_k():
    from app.services.vector_store import retrieve_context
    docs = retrieve_context("test query", top_k=3)
    assert len(docs) <= 3
