"""
Async retry wrapper with exponential backoff and jitter for transient failures.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.errors import LLMRateLimitedError, LLMUpstreamTimeoutError
from app.jobs import Job

RETRYABLE_EXCEPTIONS = (LLMRateLimitedError, LLMUpstreamTimeoutError)

T = TypeVar("T")


async def with_retry(
    coro_fn: Callable[[], Awaitable[T]],
    job: Job,
    max_attempts: int,
    base_delay: float = 1.0,
    on_attempt: Callable[[Job], None] | None = None,
) -> T:
    """
    Execute coroutine with retry on rate limit/timeout.
    coro_fn is called each attempt (fresh coroutine). Exponential backoff + jitter.
    Increments job.attempts on each attempt.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            result = await coro_fn()
            return result
        except RETRYABLE_EXCEPTIONS as e:
            last_exc = e
            job.attempts = attempt + 1
            if on_attempt:
                on_attempt(job)
            if attempt < max_attempts - 1:
                delay = base_delay * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                raise
    raise last_exc or RuntimeError("Retry exhausted")
