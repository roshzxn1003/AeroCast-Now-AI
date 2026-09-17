"""
AeroCast-Now AI Reliability, Security & Observability Suite.
Phase 11 Platform Hardening.
"""
from .taxonomy import (
    ErrorCode,
    AeroCastException,
    AuthenticationError,
    AuthorizationError,
    RateLimitExceededError,
    PayloadTooLargeError,
    NumericalValidationError,
    ConcurrencyLimitExceededError,
    ModelNotReadyError,
)
from .logging import (
    setup_structured_logging,
    get_logger,
    mask_sensitive_data,
    current_request_id,
    current_correlation_id,
)
from .auth import (
    UserRole,
    UserIdentity,
    authenticate_request,
    require_role,
    get_configured_api_keys,
)
from .middleware import (
    CorrelationIdMiddleware,
    SecurityHeadersMiddleware,
    PayloadSizeLimitMiddleware,
    RateLimitMiddleware,
    global_exception_handler,
    rate_limiter,
)
from .concurrency import inference_limiter, InferenceConcurrencyLimiter
from .health import (
    ReadinessState,
    ComponentHealthEngine,
    make_health_response,
    make_live_response,
    make_ready_response,
)
from .warmup import ModelWarmupEngine, WarmupResult
from .numerical import NumericalSafetyValidator
from .db_resilience import (
    execute_with_retry,
    atomic_transaction,
    IdempotencyLedger,
)
from .jobs import JobStatus, JobManager, job_manager
from .resource_monitor import ResourceMonitor

__all__ = [
    "ErrorCode",
    "AeroCastException",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitExceededError",
    "PayloadTooLargeError",
    "NumericalValidationError",
    "ConcurrencyLimitExceededError",
    "ModelNotReadyError",
    "setup_structured_logging",
    "get_logger",
    "mask_sensitive_data",
    "current_request_id",
    "current_correlation_id",
    "UserRole",
    "UserIdentity",
    "authenticate_request",
    "require_role",
    "get_configured_api_keys",
    "CorrelationIdMiddleware",
    "SecurityHeadersMiddleware",
    "PayloadSizeLimitMiddleware",
    "RateLimitMiddleware",
    "global_exception_handler",
    "rate_limiter",
    "inference_limiter",
    "InferenceConcurrencyLimiter",
    "ReadinessState",
    "ComponentHealthEngine",
    "make_health_response",
    "make_live_response",
    "make_ready_response",
    "ModelWarmupEngine",
    "WarmupResult",
    "NumericalSafetyValidator",
    "execute_with_retry",
    "atomic_transaction",
    "IdempotencyLedger",
    "JobStatus",
    "JobManager",
    "job_manager",
    "ResourceMonitor",
]
