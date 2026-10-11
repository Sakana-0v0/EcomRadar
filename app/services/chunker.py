import re
from typing import Iterator

def chunk_text(text: str, chunk_size: int = 600, overlap_size: int = 90) -> list[str]:
    """Split text by Chinese sentence boundaries with overlapping windows.

    Args:
        text: Input text to chunk
        chunk_size: Target size for each chunk (in characters)
        overlap_size: Overlap between consecutive chunks

    Returns:
        List of text chunks
    """
    sentences = re.split(r'(?<=[。！？])', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= chunk_size:
            current += sentence
        else:
            if current:
                chunks.append(current)
            overlap = current[-overlap_size:] if len(current) > overlap_size else current
            current = overlap + sentence
    if current:
        chunks.append(current)
    return chunks
