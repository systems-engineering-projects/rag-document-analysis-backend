"""
Cosine similarity for vector comparison in retrieval.
Returns value in [-1, 1]; zero vectors yield 0.0 to avoid division by zero.
"""

from math import sqrt


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine of the angle between two vectors. Same length required."""
    if len(a) != len(b):
        raise ValueError(
            f"Vector length mismatch: len(a)={len(a)}, len(b)={len(b)}"
        )
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = sqrt(sum(x**2 for x in a))
    norm_b = sqrt(sum(x**2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
