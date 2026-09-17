"""
Structured JSON Logging & Distributed Context Tracing for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability, Security & Observability.

Features:
- Structured JSON output with machine-parsable fields.
- ContextVar-based Request ID and Correlation ID propagation.
- Comprehensive secret masking filter (strips Bearer tokens, API keys, passwords).
"""
from __future__ import annotations

import re
import json
import logging
import sys
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Optional, Any, Dict

# Context variables for distributed request tracing
current_request_id: ContextVar[Optional[str]] = ContextVar("current_request_id", default=None)
current_correlation_id: ContextVar[Optional[str]] = ContextVar("current_correlation_id", default=None)

# Patterns for masking secrets in log messages (pattern, replacement)
SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/=]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"(?i)(api[-_]?key|token|password|secret|authorization)\s*[:=]\s*['\"]?([^'\"\s,;]+)", re.IGNORECASE), r"\1: [REDACTED]"),
]


def mask_sensitive_data(text: str) -> str:
    """Masks credentials, authorization tokens, and API keys."""
    if not isinstance(text, str):
        text = str(text)
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as uniform, machine-readable JSON objects."""

    def __init__(self, service_name: str = "aerocast-backend"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        req_id = current_request_id.get() or getattr(record, "request_id", None)
        corr_id = current_correlation_id.get() or getattr(record, "correlation_id", None)

        msg = record.getMessage()
        msg_masked = mask_sensitive_data(msg)

        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": msg_masked,
        }

        if req_id:
            log_data["request_id"] = req_id
        if corr_id:
            log_data["correlation_id"] = corr_id

        # Attach custom extra fields if provided
        if hasattr(record, "event"):
            log_data["event"] = record.event
        if hasattr(record, "component"):
            log_data["component"] = record.component
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "model_version"):
            log_data["model_version"] = record.model_version
        if hasattr(record, "data_mode"):
            log_data["data_mode"] = record.data_mode

        # If an exception was logged, record error details without leaking secrets
        if record.exc_info:
            log_data["exception"] = mask_sensitive_data(self.formatException(record.exc_info))

        return json.dumps(log_data)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configures root logger with StructuredJSONFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Retrieves a logger instance."""
    return logging.getLogger(name)
