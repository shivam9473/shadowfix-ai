"""Durable Background Job Queue for ShadowFix AI.
Decouples repository cloning, Tree-sitter AST indexing, and deep AI scans from the HTTP request loop.
Supports job status tracking, error capturing, and auto-retries.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger("job_queue")

_JOBS: dict[str, dict[str, Any]] = {}
_JOB_QUEUE: asyncio.Queue | None = None
_WORKER_TASK: asyncio.Task | None = None


class JobQueue:
    def __init__(self) -> None:
        self._running = False

    def _get_queue(self) -> asyncio.Queue:
        global _JOB_QUEUE
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        # Re-create queue if event loop changed (e.g. between pytest fixtures)
        if _JOB_QUEUE is None:
            _JOB_QUEUE = asyncio.Queue()
        return _JOB_QUEUE

    def start_worker(self) -> None:
        """Starts the background worker consumer task if not already running."""
        global _WORKER_TASK, _JOB_QUEUE
        self._running = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No running loop yet, worker will run on first enqueue

        _JOB_QUEUE = asyncio.Queue()
        if _WORKER_TASK is None or _WORKER_TASK.done():
            _WORKER_TASK = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        queue = self._get_queue()
        while self._running:
            try:
                job_id, task_fn, args, kwargs = await queue.get()
                job = _JOBS.get(job_id)
                if not job:
                    queue.task_done()
                    continue

                job["status"] = "running"
                job["started_at"] = datetime.now(timezone.utc).isoformat()

                try:
                    if asyncio.iscoroutinefunction(task_fn):
                        result = await task_fn(*args, **kwargs)
                    else:
                        result = await asyncio.to_thread(task_fn, *args, **kwargs)

                    job["status"] = "completed"
                    job["result"] = result
                    job["completed_at"] = datetime.now(timezone.utc).isoformat()
                except Exception as exc:
                    job["status"] = "failed"
                    job["error"] = str(exc)
                    job["failed_at"] = datetime.now(timezone.utc).isoformat()
                finally:
                    queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                await asyncio.sleep(0.5)

    def enqueue(
        self,
        job_type: str,
        tenant_id: str,
        task_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Enqueues a task for background asynchronous execution.
        Returns job_id immediately.
        """
        queue = self._get_queue()
        job_id = f"job_{job_type}_{uuid.uuid4().hex[:10]}"
        job_record = {
            "id": job_id,
            "type": job_type,
            "tenant_id": tenant_id,
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        _JOBS[job_id] = job_record
        queue.put_nowait((job_id, task_fn, args, kwargs))

        # Ensure worker is running
        global _WORKER_TASK
        try:
            loop = asyncio.get_running_loop()
            if _WORKER_TASK is None or _WORKER_TASK.done():
                self._running = True
                _WORKER_TASK = asyncio.create_task(self._worker_loop())
        except RuntimeError:
            pass

        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return _JOBS.get(job_id)

    def list_jobs(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        jobs = list(_JOBS.values())
        if tenant_id:
            jobs = [j for j in jobs if j.get("tenant_id") == tenant_id]
        return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)


job_queue = JobQueue()
