"""
Token bucket rate limiter: async-safe, in-memory. Throttles LLM calls.
"""

import asyncio
import logging
import time

from app.config import LLM_RATE_LIMIT_SECONDS, LLM_TOKEN_LIMIT
from app.errors import LLMRateLimitedError

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Token bucket: X tokens per Y seconds, refill over time.
    Async-safe via asyncio.Lock.
    """

    def __init__(
        self,
        tokens: int = LLM_TOKEN_LIMIT,
        refill_seconds: int = LLM_RATE_LIMIT_SECONDS,
    ) -> None:
        self._tokens = float(tokens)
        self._max_tokens = float(tokens)
        self._refill_rate = tokens / refill_seconds
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Consume one token. Raises LLMRateLimitedError if no tokens available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self._max_tokens,
                self._tokens + elapsed * self._refill_rate,
            )
            self._last_refill = now
            if self._tokens < 1:
                logger.warning("rate_limiter: no tokens available, rejecting")
                raise LLMRateLimitedError("No tokens available")
            self._tokens -= 1
