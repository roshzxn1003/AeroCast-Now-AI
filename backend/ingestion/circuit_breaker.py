"""
Circuit Breaker & Exponential Backoff for Upstream Meteorological Providers.
Phase 9 Operational Data Infrastructure — Protects Upstream APIs and Ensures Stability.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any

logger = logging.getLogger("aerocast.ingestion.circuit_breaker")

class CircuitState(str, Enum):
    HEALTHY = "HEALTHY"       # Normal operation (closed)
    DEGRADED = "DEGRADED"     # Intermittent errors detected
    OPEN = "OPEN"             # Tripped: requests blocked to allow upstream recovery
    HALF_OPEN = "HALF_OPEN"   # Probing single trial request after cooldown

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3          # Consecutive failures to trip OPEN
    cooldown_seconds: float = 30.0      # Time before attempting HALF_OPEN probe
    timeout_seconds: float = 5.0        # Individual request timeout
    max_retries: int = 2                # Max immediate retries with backoff
    backoff_factor: float = 0.5         # Exponential multiplier (0.5s, 1.0s)

class CircuitBreaker:
    """Stateful circuit breaker with exponential backoff for a specific provider."""

    def __init__(self, provider_id: str, config: Optional[CircuitBreakerConfig] = None):
        self.provider_id = provider_id
        self.config = config or CircuitBreakerConfig()
        self.state: CircuitState = CircuitState.HEALTHY
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.total_requests: int = 0
        self.total_failures: int = 0
        self.last_failure_time: float = 0.0
        self.last_success_time: float = 0.0
        self.last_trip_time: float = 0.0
        self.last_error: Optional[str] = None

    def can_execute(self) -> bool:
        """Determines if a request is allowed to proceed."""
        now = time.time()
        if self.state == CircuitState.OPEN:
            if (now - self.last_trip_time) >= self.config.cooldown_seconds:
                logger.info(f"CircuitBreaker[{self.provider_id}]: Cooldown expired. Entering HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self, latency_ms: float = 0.0):
        """Records a successful operation, recovering the circuit if in HALF_OPEN."""
        now = time.time()
        self.last_success_time = now
        self.total_requests += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1

        if self.state in (CircuitState.HALF_OPEN, CircuitState.DEGRADED):
            logger.info(f"CircuitBreaker[{self.provider_id}]: Success recorded. Recovering to HEALTHY.")
            self.state = CircuitState.HEALTHY

    def record_failure(self, error_message: str):
        """Records a failure and transitions circuit state if thresholds are breached."""
        now = time.time()
        self.last_failure_time = now
        self.last_error = error_message
        self.total_requests += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"CircuitBreaker[{self.provider_id}]: Probe failed in HALF_OPEN. Tripping back to OPEN.")
            self.state = CircuitState.OPEN
            self.last_trip_time = now
        elif self.consecutive_failures >= self.config.failure_threshold:
            logger.error(
                f"CircuitBreaker[{self.provider_id}]: {self.consecutive_failures} consecutive failures. "
                f"Tripping circuit to OPEN for {self.config.cooldown_seconds}s."
            )
            self.state = CircuitState.OPEN
            self.last_trip_time = now
        else:
            self.state = CircuitState.DEGRADED

    def get_metrics(self) -> dict:
        now = time.time()
        cooldown_remaining = max(0.0, self.config.cooldown_seconds - (now - self.last_trip_time)) if self.state == CircuitState.OPEN else 0.0
        error_rate = (self.total_failures / self.total_requests) if self.total_requests > 0 else 0.0
        return {
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "error_rate": round(error_rate, 3),
            "cooldown_remaining_sec": round(cooldown_remaining, 1),
            "last_error": self.last_error,
        }
