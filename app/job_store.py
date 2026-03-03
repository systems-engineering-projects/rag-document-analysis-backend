"""
In-memory job store with async-safe concurrent access (asyncio.Lock).
"""

import asyncio
import uuid
from datetime import datetime, timezone

from app.jobs import Job, JobStatus


class JobStore:
    """
    In-memory job store. Safe for concurrent access via asyncio.Lock.
    Each submission creates a new job (no duplicate text detection).
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, text: str) -> Job:
        """Create a new job with unique ID. Each submission gets a new job_id."""
        job_id = uuid.uuid4().hex
        newjob = Job(
            id=job_id,
            text=text,
            status=JobStatus.PENDING,
            )
        async with self._lock:
            if job_id in self._jobs:
                raise ValueError(f"Duplicate id: {job_id}")
            self._jobs[job_id] = newjob
        return newjob


    async def get_job(self, job_id) -> Job:
        current_job = self._jobs.get(job_id)
        return current_job

    async def update_job(self, job: Job) -> Job | None:
        job.updated_at = datetime.now(timezone.utc)
        async with self._lock:
            if job.id in self._jobs:
                self._jobs[job.id] = job
                return job
            else: 
                return None

        
    async def list_pending(self) -> list[Job]:
        """Return jobs with status PENDING, ordered by created_at."""
        async with self._lock:
            pending = [j for j in self._jobs.values() if j.status == JobStatus.PENDING]
        return sorted(pending, key= lambda j: j.created_at)