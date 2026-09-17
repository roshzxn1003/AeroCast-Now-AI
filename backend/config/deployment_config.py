"""
AeroCast-Now AI: Deployment & Environment Configuration Architecture
====================================================================
Formal separation of environments: development, testing, staging, production.
Enforces startup validation and Fail-Fast guarantees.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class EnvironmentType(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigurationError(Exception):
    """Raised when configuration validation fails, triggering Fail-Fast shutdown."""
    pass


# Default insecure tokens that are strictly rejected in production
INSECURE_TEST_TOKENS = {
    "admin_secret_token",
    "test_token",
    "supersecret_test_token_change_in_prod",
    "default_insecure_token",
    "password",
    "12345678",
    "aerocast_admin"
}


@dataclass
class DeploymentConfig:
    """Central deployment and runtime configuration with environment isolation."""

    env: EnvironmentType = field(default=EnvironmentType.DEVELOPMENT)
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = ""
    data_dir: str = ""
    admin_token: str = ""
    secret_key: str = ""
    allowed_origins: List[str] = field(default_factory=lambda: ["http://localhost:5173", "http://localhost:8000"])
    data_mode: str = "hybrid"  # 'real', 'hybrid', 'simulation'
    log_level: str = "INFO"
    rate_limit_enabled: bool = True
    max_inference_concurrency: int = 2
    model_weights_path: str = ""

    @classmethod
    def from_env(cls) -> "DeploymentConfig":
        """Loads and resolves deployment configuration from environment variables."""
        raw_env = os.getenv("AEROCAST_ENV", os.getenv("ENV", "development")).lower()
        try:
            env_type = EnvironmentType(raw_env)
        except ValueError:
            raise ConfigurationError(
                f"Invalid AEROCAST_ENV '{raw_env}'. Must be one of: "
                f"{[e.value for e in EnvironmentType]}"
            )

        base_dir = Path(__file__).parent.parent.resolve()
        
        # Default storage directory based on environment
        default_data_dir = str(base_dir.parent / "data")
        data_dir = os.getenv("AEROCAST_DATA_DIR", default_data_dir)

        # Database path separation
        db_env_override = os.getenv("AEROCAST_DB_PATH")
        if db_env_override:
            db_path = db_env_override
        else:
            if env_type == EnvironmentType.PRODUCTION:
                db_path = str(Path(data_dir) / "aerocast.sqlite3")
            elif env_type == EnvironmentType.STAGING:
                db_path = str(Path(data_dir) / "staging" / "aerocast_staging.sqlite3")
            elif env_type == EnvironmentType.TESTING:
                db_path = str(Path(data_dir) / "testing" / "aerocast_testing.sqlite3")
            else:
                db_path = str(Path(data_dir) / "aerocast.sqlite3")

        # Admin token
        admin_token = os.getenv("AEROCAST_ADMIN_TOKEN", "")
        secret_key = os.getenv("AEROCAST_SECRET_KEY", "")

        # CORS
        raw_cors = os.getenv("CORS_ORIGINS", "")
        if raw_cors:
            allowed_origins = [orig.strip() for orig in raw_cors.split(",") if orig.strip()]
        else:
            if env_type == EnvironmentType.PRODUCTION:
                allowed_origins = ["https://aerocast.in", "https://app.aerocast.in"]
            elif env_type == EnvironmentType.STAGING:
                allowed_origins = ["http://staging.aerocast.local:5173", "http://localhost:5173", "http://localhost:8080"]
            else:
                allowed_origins = ["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:5173", "http://127.0.0.1:8000"]

        # Log Level
        log_level = os.getenv("LOG_LEVEL", "DEBUG" if env_type == EnvironmentType.DEVELOPMENT else "INFO")

        # Data Mode
        data_mode = os.getenv("DATA_MODE", "real" if env_type == EnvironmentType.PRODUCTION else "hybrid").lower()

        # Model Weights Path
        default_model = str(base_dir / "models" / "convlstm_real_best.keras")
        model_weights_path = os.getenv("AEROCAST_MODEL_PATH", default_model)

        config = cls(
            env=env_type,
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            db_path=db_path,
            data_dir=data_dir,
            admin_token=admin_token,
            secret_key=secret_key,
            allowed_origins=allowed_origins,
            data_mode=data_mode,
            log_level=log_level,
            rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            max_inference_concurrency=int(os.getenv("MAX_CONCURRENT_INFERENCES", "2")),
            model_weights_path=model_weights_path,
        )
        return config

    def validate(self) -> None:
        """
        Validates configuration integrity and executes Fail-Fast assertions.
        Prevents dangerous environment cross-contamination.
        """
        # Rule 6 & 8: Never allow production application to connect to development/testing database
        if self.env == EnvironmentType.PRODUCTION:
            lower_db = self.db_path.lower()
            if "test" in lower_db or "dev" in lower_db or "sample" in lower_db:
                raise ConfigurationError(
                    f"FAIL FAST: Production environment cannot use dev/test database: {self.db_path}"
                )

            # Rule 9: Never deploy synthetic data as REAL data in production
            if self.data_mode == "simulation":
                raise ConfigurationError(
                    "FAIL FAST: Production environment cannot operate in 'simulation' DATA_MODE. "
                    "Must be 'real' or 'hybrid'."
                )

            # Rule 7 & 8: Never commit secrets or run with default/insecure credentials
            if not self.admin_token:
                raise ConfigurationError(
                    "FAIL FAST: Production environment requires AEROCAST_ADMIN_TOKEN to be set."
                )
            if self.admin_token.strip() in INSECURE_TEST_TOKENS or len(self.admin_token) < 16:
                raise ConfigurationError(
                    "FAIL FAST: Production AEROCAST_ADMIN_TOKEN is insecure or shorter than 16 characters."
                )

            if not self.secret_key or len(self.secret_key) < 24:
                raise ConfigurationError(
                    "FAIL FAST: Production AEROCAST_SECRET_KEY is missing or shorter than 24 characters."
                )

            # Model weights validation in production
            if not os.path.exists(self.model_weights_path):
                raise ConfigurationError(
                    f"FAIL FAST: Production model weights file not found: {self.model_weights_path}"
                )
            if os.path.getsize(self.model_weights_path) < 1000000:
                raise ConfigurationError(
                    f"FAIL FAST: Production model weights file appears corrupted or empty (< 1MB): {self.model_weights_path}"
                )

        elif self.env == EnvironmentType.STAGING:
            if "aerocast.sqlite3" in Path(self.db_path).name and "staging" not in self.db_path:
                raise ConfigurationError(
                    f"FAIL FAST: Staging environment cannot point directly to production database: {self.db_path}"
                )

        elif self.env == EnvironmentType.TESTING:
            if "aerocast.sqlite3" == Path(self.db_path).name and "test" not in self.db_path:
                raise ConfigurationError(
                    f"FAIL FAST: Testing environment cannot point directly to production database: {self.db_path}"
                )

        # Storage directory write verification
        db_parent = Path(self.db_path).parent
        try:
            db_parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigurationError(
                f"FAIL FAST: Cannot create database parent directory {db_parent}: {e}"
            )


# Global singleton instance loaded once
_CURRENT_CONFIG: Optional[DeploymentConfig] = None


def get_deployment_config() -> DeploymentConfig:
    global _CURRENT_CONFIG
    if _CURRENT_CONFIG is None:
        _CURRENT_CONFIG = DeploymentConfig.from_env()
    return _CURRENT_CONFIG


def reload_deployment_config() -> DeploymentConfig:
    global _CURRENT_CONFIG
    _CURRENT_CONFIG = DeploymentConfig.from_env()
    return _CURRENT_CONFIG
