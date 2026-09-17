"""
Production Middleware & Security Interceptors for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability, Security & Observability.

Includes:
1. Correlation & Request ID Middleware (distributed context tracing).
2. HTTP Security Headers Middleware (OWASP security compliance).
3. Payload Size Limiting Middleware (anti-DoS protection).
4. Sliding-Window Rate Limiting Middleware.
5. Global Exception Interceptor & Sanitized Error Handler.
"""
from __future__ import annotations

import time
import uuid
import logging
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .logging import current_request_id, current_correlation_id, get_logger
from .taxonomy import AeroCastException, ErrorCode, RateLimitExceededError, PayloadTooLargeError

logger = get_logger("aerocast.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Generates or propagates Request-ID and Correlation-ID across all requests."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        corr_id = request.headers.get("X-Correlation-ID") or req_id

        # Bind context variables for structured logging
        current_request_id.set(req_id)
        current_correlation_id.set(corr_id)
        request.state.request_id = req_id
        request.state.correlation_id = corr_id

        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000.0, 2)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Correlation-ID"] = corr_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces strict OWASP security headers on all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), microphone=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Protects against memory exhaustion attacks by bounding incoming payload size."""

    def __init__(self, app, max_bytes: int = 10 * 1024 * 1024):  # Default: 10MB
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": True,
                            "error_code": ErrorCode.PAYLOAD_TOO_LARGE.value,
                            "message": f"Payload size ({length} bytes) exceeds limit of {self.max_bytes} bytes",
                            "correlation_id": getattr(request.state, "correlation_id", None),
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)


class RateLimiter:
    """Sliding-window in-memory rate limiter with per-tier limits."""

    def __init__(self):
        # key -> list of timestamp floats
        self._requests: Dict[str, List[float]] = defaultdict(list)
        # Tier limits: (max_requests, window_seconds)
        self.limits = {
            "default": (120, 60),      # 120 req/min for public
            "inference": (30, 60),     # 30 req/min for compute-heavy ML
            "admin": (60, 60),         # 60 req/min for management
        }

    def is_allowed(self, client_key: str, tier: str = "default") -> Tuple[bool, int]:
        max_req, window = self.limits.get(tier, self.limits["default"])
        now = time.time()
        cutoff = now - window

        # Filter out old requests
        timestamps = [t for t in self._requests[client_key] if t > cutoff]
        self._requests[client_key] = timestamps

        if len(timestamps) >= max_req:
            retry_after = int(window - (now - timestamps[0])) + 1
            return False, max(1, retry_after)

        self._requests[client_key].append(now)
        return True, 0


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies tiered rate limiting based on client IP / path."""

    async def dispatch(self, request: Request, call_next):
        # Skip health / readiness checks from rate limiting
        if request.url.path in ("/health", "/ready", "/live", "/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        tier = "default"
        if "/predict" in request.url.path or "/inference" in request.url.path:
            tier = "inference"
        elif "/admin" in request.url.path or "/promote" in request.url.path or "/rollback" in request.url.path:
            tier = "admin"

        client_key = f"{client_ip}:{tier}"
        allowed, retry_after = rate_limiter.is_allowed(client_key, tier)

        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "error": True,
                    "error_code": ErrorCode.RATE_LIMIT_ERROR.value,
                    "message": "Too many requests. Please slow down.",
                    "retry_after_seconds": retry_after,
                    "correlation_id": getattr(request.state, "correlation_id", None),
                },
            )

        return await call_next(request)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Centralized exception interceptor.
    Prevents leaking internal stack traces to clients while logging full details internally.
    """
    corr_id = getattr(request.state, "correlation_id", None) or "unknown"
    req_id = getattr(request.state, "request_id", None) or "unknown"

    if isinstance(exc, AeroCastException):
        logger.warning(
            f"Handled operational exception: {exc.message}",
            extra={"error_code": exc.error_code.value, "request_id": req_id, "correlation_id": corr_id},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    # Unhandled / System Exceptions
    logger.error(
        f"Unhandled application exception on {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
        extra={"request_id": req_id, "correlation_id": corr_id},
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": "An unexpected internal error occurred. Operators have been notified.",
            "correlation_id": corr_id,
        },
    )
