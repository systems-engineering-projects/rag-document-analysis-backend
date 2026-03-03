"""
Embedder abstraction: list of strings → list of vectors. Uses OpenAI when OPENAI_API_KEY is set,
with optional fallback to Ollama; otherwise Ollama only.
"""

import logging
from dataclasses import dataclass

from app.config import (
    EMBED_FALLBACK_TO_LOCAL,
    EMBED_LOCAL_ONLY,
    EMBED_MODEL,
    OPENAI_API_KEY,
)
from app.embeddings_client import embed_texts as embed_texts_ollama
from app.embeddings_openai import (
    OPENAI_EMBED_DIMENSIONS,
    OPENAI_EMBED_MODEL,
    embed_texts_openai,
)

logger = logging.getLogger(__name__)

DIM_FOR_MODEL = {"nomic-embed-text": 768, OPENAI_EMBED_MODEL: OPENAI_EMBED_DIMENSIONS}


@dataclass
class Embedder:
    """Model name and vector dimension for the embedder."""

    model: str
    dim: int


class HttpEmbedder(Embedder):
    """Uses OpenAI when OPENAI_API_KEY is set and not EMBED_LOCAL_ONLY, else Ollama. Optional fallback to Ollama on OpenAI failure."""

    def __init__(self, model: str | None = None, dim: int | None = None):
        use_openai = bool(OPENAI_API_KEY) and not EMBED_LOCAL_ONLY
        if use_openai:
            model = model or OPENAI_EMBED_MODEL
            dim = dim or OPENAI_EMBED_DIMENSIONS
        else:
            model = model or EMBED_MODEL
            dim = dim or DIM_FOR_MODEL.get(model, 768)
        super().__init__(model=model, dim=dim)
        self._use_openai = use_openai

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed texts; returns one vector per text in order. Tries OpenAI first when key set; optional Ollama fallback."""
        if self._use_openai:
            try:
                return await embed_texts_openai(texts)
            except Exception as e:
                if EMBED_FALLBACK_TO_LOCAL:
                    logger.warning("OpenAI embedding failed, falling back to local: %s", e)
                    return await embed_texts_ollama(texts)
                raise
        return await embed_texts_ollama(texts)
