"""
Embedding API client: batched embed with timeout and retries (exponential backoff + jitter).
Uses Ollama /api/embed by default; supports OpenAI-style response shapes.
"""

import asyncio
import logging
import random

import httpx

from app.config import (
    EMBED_BASE_URL,
    EMBED_MAX_ATTEMPTS,
    EMBED_MODEL,
    EMBED_TIMEOUT,
)
from app.errors import (
    LLMRateLimitedError,
    LLMServiceError,
    LLMUpstreamTimeoutError,
)

logger = logging.getLogger(__name__)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts in one batched request. Returns one vector per text, same order.
    Uses timeout and retries (exponential backoff + jitter) on rate limit / timeout.
    """
    if not texts:
        return []

    last_exc: BaseException | None = None
    for attempt in range(EMBED_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as client:
                response = await client.post(
                    f"{EMBED_BASE_URL}/api/embed",
                    headers={"Content-Type": "application/json"},
                    json={"model": EMBED_MODEL, "input": texts},
                )
            if response.status_code == 429:
                raise LLMRateLimitedError("Embedding API rate limited")
            if response.status_code >= 400:
                raise LLMServiceError(
                    f"Embedding API error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
        except httpx.TimeoutException:
            last_exc = LLMUpstreamTimeoutError("Embedding request timed out")
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
    else:
        if last_exc:
            raise last_exc
        raise RuntimeError("Embedding retries exhausted")

    if data.get("embeddings"):
        return data["embeddings"]
    if data.get("embedding") is not None:
        return [data["embedding"]]
    raise LLMServiceError("Unexpected embed response shape")
