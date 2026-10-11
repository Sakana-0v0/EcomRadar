import pytest

def test_chunk_by_sentence():
    from app.services.chunker import chunk_text
    text = "这是第一句。这是第二句。这是第三句。"
    chunks = chunk_text(text, chunk_size=10, overlap_size=3)
    assert len(chunks) > 1
