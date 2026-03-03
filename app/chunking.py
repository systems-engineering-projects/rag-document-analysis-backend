"""
Split text into overlapping chunks by character count for embedding/retrieval.
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    """One chunk of text with indices into the original document."""

    chunk_index: int
    content: str
    start_offset: int
    end_offset: int


def chunk_text_chars(text: str, chunk_size: int, overlap: int) -> list[Chunk]:
    """
    Split text into overlapping chunks. Step = chunk_size - overlap.
    Last chunk may be shorter. Overlap must be < chunk_size.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk size")

    list_of_chunks = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunk_index = len(list_of_chunks)
        list_of_chunks.append(
            Chunk(
                chunk_index=chunk_index,
                content=chunk,
                start_offset=start,
                end_offset=end,
            )
        )
    return list_of_chunks
