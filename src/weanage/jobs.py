"""Minimal in-process job queue so long analyses report progress to the UI."""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

MAX_JOBS_KEPT = 50


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"  # queued | running | done | error
    done: int = 0
    total: int = 0
    message: str = ""
    result: Any = None
    error: str | None = None
    created: float = field(default_factory=time.time)

    def snapshot(self, with_result: bool = True) -> dict:
        out = {
            "id": self.id, "kind": self.kind, "status": self.status, "done": self.done,
            "total": self.total, "message": self.message, "error": self.error,
        }
        if with_result and self.status == "done":
            out["result"] = self.result
        return out


class JobQueue:
    def __init__(self, workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="weanage-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[Callable[[int, int], None]], Any]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job
            for old in sorted(self._jobs.values(), key=lambda j: j.created)[:-MAX_JOBS_KEPT]:
                self._jobs.pop(old.id, None)

        def progress(done: int, total: int) -> None:
            job.done, job.total = done, total

        def run() -> None:
            job.status = "running"
            try:
                job.result = fn(progress)
                job.status = "done"
            except Exception as exc:  # surfaced to the UI rather than lost in a thread
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                job.message = traceback.format_exc(limit=3)

        self._pool.submit(run)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
