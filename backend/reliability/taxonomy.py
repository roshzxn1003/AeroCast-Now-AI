"""
AeroCast-Now AI Unified Error Taxonomy & Operational Exceptions.
Phase 11 Platform Hardening — Reliability, Security & Observability.

Provides standardized operational error codes and structured exception classes.
Never exposes raw stack traces to unauthenticated clients.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(str, Enum):
    # Data Ingestion & Provider Errors
    DATA_SOURCE_ERROR = "DATA_SOURCE_ERROR"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    DATA_FRESHNESS_ERROR = "DATA_FRESHNESS_ERROR"
    DATA_COVERAGE_ERROR = "DATA_COVERAGE_ERROR"
    PROVIDER_CIRCUIT_OPEN = "PROVIDER_CIRCUIT_OPEN"
    
    # State & Persistence Errors
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_LOCKED = "DATABASE_LOCKED"
    STORAGE_ERROR = "STORAGE_ERROR"
    ARTIFACT_INTEGRITY_ERROR = "ARTIFACT_INTEGRITY_ERROR"
    
    # Model & Inference Errors
    MODEL_LOAD_ERROR = "MODEL_LOAD_ERROR"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    MODEL_INFERENCE_ERROR = "MODEL_INFERENCE_ERROR"
    NUMERICAL_VALIDATION_ERROR = "NUMERICAL_VALIDATION_ERROR"
    INFERENCE_CONCURRENCY_EXCEEDED = "INFERENCE_CONCURRENCY_EXCEEDED"
    
    # Security & Access Errors
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    INVALID_INPUT = "INVALID_INPUT"
    
    # Execution & System Errors
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    JOB_EXECUTION_ERROR = "JOB_EXECUTION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AeroCastException(Exception):
    """Base exception for all AeroCast operational and meteorological errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.correlation_id = correlation_id

    def to_dict(self, include_details: bool = True) -> Dict[str, Any]:
        res = {
            "error": True,
            "error_code": self.error_code.value,
            "message": self.message,
            "status_code": self.status_code,
        }
        if self.correlation_id:
            res["correlation_id"] = self.correlation_id
        if include_details and self.details:
            res["details"] = self.details
        return res


class AuthenticationError(AeroCastException):
    def __init__(self, message: str = "Authentication required or invalid credentials", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTHENTICATION_ERROR, status_code=401, details=details)


class AuthorizationError(AeroCastException):
    def __init__(self, message: str = "Insufficient permissions for requested resource", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTHORIZATION_ERROR, status_code=403, details=details)


class RateLimitExceededError(AeroCastException):
    def __init__(self, message: str = "Rate limit exceeded. Please retry later.", retry_after_seconds: int = 60):
        super().__init__(message, ErrorCode.RATE_LIMIT_ERROR, status_code=429, details={"retry_after_seconds": retry_after_seconds})


class PayloadTooLargeError(AeroCastException):
    def __init__(self, max_bytes: int, received_bytes: int):
        super().__init__(
            f"Request payload size ({received_bytes} bytes) exceeds maximum limit ({max_bytes} bytes)",
            ErrorCode.PAYLOAD_TOO_LARGE,
            status_code=413,
            details={"max_bytes": max_bytes, "received_bytes": received_bytes},
        )


class NumericalValidationError(AeroCastException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.NUMERICAL_VALIDATION_ERROR, status_code=422, details=details)


class ConcurrencyLimitExceededError(AeroCastException):
    def __init__(self, message: str = "Inference capacity saturated. Please retry shortly."):
        super().__init__(message, ErrorCode.INFERENCE_CONCURRENCY_EXCEEDED, status_code=503)


class ModelNotReadyError(AeroCastException):
    def __init__(self, message: str = "Model is currently not ready for inference."):
        super().__init__(message, ErrorCode.MODEL_NOT_READY, status_code=503)
