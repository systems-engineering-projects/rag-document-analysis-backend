"""
OpenAI embeddings API: batched embed with dimensions=768, timeout and retries.
Used when OPENAI_API_KEY is set; same dimension as nomic-embed-text for schema/fallback compatibility.
"""

import asyncio
import logging
import random

import httpx

from app.config import (
    EMBED_MAX_ATTEMPTS,
    EMBED_TIMEOUT,
    OPENAI_API_KEY,
)
from app.errors import (
    LLMRateLimitedError,
    LLMServiceError,
    LLMUpstreamTimeoutError,
)

logger = logging.getLogger(__name__)

OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"
OPENAI_EMBED_MODEL = "text-embedding-3-small"
OPENAI_EMBED_DIMENSIONS = 768
OPENAI_BATCH_SIZE = 100


async def embed_texts_openai(texts: list[str]) -> list[list[float]]:
    """
    Embed texts via OpenAI API with dimensions=768. Batches in chunks of OPENAI_BATCH_SIZE.
    Returns one vector per text in order. Retries on timeout / 429 / 5xx.
    """
    if not texts:
        return []
    if not OPENAI_API_KEY:
        raise LLMServiceError("OPENAI_API_KEY is not set")

    last_exc: BaseException | None = None
    for attempt in range(EMBED_MAX_ATTEMPTS):
        try:
            all_embeddings: list[list[float]] = []
            for i in range(0, len(texts), OPENAI_BATCH_SIZE):
                batch = texts[i : i + OPENAI_BATCH_SIZE]
                async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as client:
                    response = await client.post(
                        OPENAI_EMBED_URL,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {OPENAI_API_KEY}",
                        },
                        json={
                            "model": OPENAI_EMBED_MODEL,
                            "input": batch,
                            "dimensions": OPENAI_EMBED_DIMENSIONS,
                        },
                    )
                if response.status_code == 429:
                    logger.warning("OpenAI embedding API returned 429 (rate limited)")
                    raise LLMRateLimitedError("OpenAI embedding API rate limited")
                if response.status_code >= 400:
                    raise LLMServiceError(
                        f"OpenAI embedding API error {response.status_code}: {response.text[:200]}"
                    )
                data = response.json()
                for item in data.get("data", []):
                    emb = item.get("embedding")
                    if emb is not None:
                        all_embeddings.append(emb)
            if len(all_embeddings) != len(texts):
                raise LLMServiceError(
                    f"OpenAI returned {len(all_embeddings)} embeddings for {len(texts)} texts"
                )
            return all_embeddings
        except httpx.TimeoutException:
            last_exc = LLMUpstreamTimeoutError("OpenAI embedding request timed out")
            if attempt < EMBED_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                raise last_exc
            continue
        except (LLMRateLimitedError, LLMUpstreamTimeoutError) as e:
            last_exc = e
            if attempt < EMBED_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                raise
            continue
        except LLMServiceError:
            raise
        break

    if last_exc:
        raise last_exc
    raise RuntimeError("OpenAI embedding retries exhausted")
