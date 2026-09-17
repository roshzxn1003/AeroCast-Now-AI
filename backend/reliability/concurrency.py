"""
Inference Concurrency Limiter & Overload Protection for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability & Resource Protection.

Bounds concurrent model execution to prevent CPU/GPU saturation and memory exhaustion.
Provides non-blocking load shedding with HTTP 503 when capacity is saturated.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional
from contextlib import asynccontextmanager

from .taxonomy import ConcurrencyLimitExceededError


class InferenceConcurrencyLimiter:
    """Limits simultaneous ML inference executions using an asyncio semaphore."""

    def __init__(self, max_concurrent: Optional[int] = None, timeout_seconds: float = 2.0):
        if max_concurrent is None:
            max_concurrent = int(os.getenv("AEROCAST_MAX_CONCURRENT_INFERENCE", "2"))
        self.max_concurrent = max(1, max_concurrent)
        self.timeout_seconds = timeout_seconds
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_count = 0
        self._peak_count = 0
        self._total_rejected = 0

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    @asynccontextmanager
    async def acquire(self):
        sem = self._get_semaphore()
        try:
            # Wait up to timeout_seconds for an inference slot
            acquired = await asyncio.wait_for(sem.acquire(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            self._total_rejected += 1
            raise ConcurrencyLimitExceededError(
                f"Inference queue saturated ({self._active_count}/{self.max_concurrent} active). Try again in a few seconds."
            )

        self._active_count += 1
        self._peak_count = max(self._peak_count, self._active_count)
        try:
            yield
        finally:
            self._active_count -= 1
            sem.release()

    def get_stats(self):
        return {
            "max_concurrent": self.max_concurrent,
            "active_inferences": self._active_count,
            "peak_concurrent": self._peak_count,
            "total_rejected": self._total_rejected,
        }


# Global singleton limiter
inference_limiter = InferenceConcurrencyLimiter()
