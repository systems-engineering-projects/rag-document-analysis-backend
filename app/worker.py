"""
Background worker loop: fetches pending jobs, processes with rate limit and retry.
"""

import asyncio
import logging

from app.config import LLM_MAX_ATTEMPTS, LLM_TIMEOUT_SECONDS
from app.errors import LLMRateLimitedError, LLMUpstreamTimeoutError
from app.job_store import JobStore
from app.jobs import Job, JobStatus
from app.rate_limit import TokenBucket
from app.retry import with_retry

from app import llm_client

logger = logging.getLogger(__name__)


async def _process_job(
    job_store: JobStore,
    rate_limiter: TokenBucket,
    job: Job,
) -> None:
    """Process a single job: rate limit, call LLM, update status."""

    async def _do_answer() -> str:
        while True:
            try:
                await rate_limiter.acquire()
                break
            except LLMRateLimitedError:
                await asyncio.sleep(1)
        try:
            return await asyncio.wait_for(
                llm_client.answer_with_context(job.text),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as e:
            raise LLMUpstreamTimeoutError("LLM call timed out") from e

    try:
        result = await with_retry(
            _do_answer,
            job,
            max_attempts=LLM_MAX_ATTEMPTS,
        )
        job.status = JobStatus.SUCCESS
        job.result = result
    except (LLMUpstreamTimeoutError, Exception):
        job.status = JobStatus.FAILED
        logger.error("Job %s failed after %d attempts", job.id, job.attempts)
    await job_store.update_job(job)


async def worker_loop(
    job_store: JobStore,
    rate_limiter: TokenBucket,
) -> None:
    """
    Background worker: fetch pending jobs, process one at a time.
    Does not crash on single job failure.
    """
    while True:
        try:
            pending = await job_store.list_pending()
            for job in pending[:1]:
                try:
                    job.status = JobStatus.RUNNING
                    await job_store.update_job(job)
                    await _process_job(job_store, rate_limiter, job)
                except Exception as e:
                    logger.error("Unexpected error processing job %s: %s", job.id, e)
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    await job_store.update_job(job)
        except Exception as e:
            logger.error("Worker loop error: %s", e)
        await asyncio.sleep(0.5)
