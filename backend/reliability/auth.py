"""
Role-Based Access Control (RBAC) & API Key Authentication for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability & Security.

Roles:
- VIEWER: Read-only access to public nowcasts, weather maps, and bulletins.
- RESEARCHER: Access to historical verification datasets, model drift metrics, and experiments.
- OPERATOR: Operational privileges to acknowledge alerts, trigger fallbacks, and manage providers.
- ADMIN: Privileged operations (model promotion, model rollback, retraining approval, configuration).
"""
from __future__ import annotations

import os
import secrets
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict
from fastapi import Request, Header, HTTPException, Depends

from .taxonomy import AuthenticationError, AuthorizationError


class UserRole(str, Enum):
    VIEWER = "VIEWER"
    RESEARCHER = "RESEARCHER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


# Role hierarchy mapping: higher roles inherit lower role permissions
ROLE_HIERARCHY: Dict[UserRole, int] = {
    UserRole.VIEWER: 1,
    UserRole.RESEARCHER: 2,
    UserRole.OPERATOR: 3,
    UserRole.ADMIN: 4,
}


@dataclass
class UserIdentity:
    username: str
    role: UserRole
    api_key_prefix: str


# Pre-configured keys from environment or secure defaults for development
def get_configured_api_keys() -> Dict[str, UserIdentity]:
    """
    Returns active API key mapping from environment variables.
    Format: AEROCAST_KEY_<USERNAME>=<KEY>:<ROLE>
    Provides fallback development keys if none configured.
    """
    keys: Dict[str, UserIdentity] = {}
    
    # Check environment for explicit keys
    for k, v in os.environ.items():
        if k.startswith("AEROCAST_KEY_") and ":" in v:
            parts = v.split(":", 1)
            token, role_str = parts[0].strip(), parts[1].strip().upper()
            username = k.replace("AEROCAST_KEY_", "").lower()
            role = getattr(UserRole, role_str, UserRole.VIEWER)
            keys[token] = UserIdentity(username=username, role=role, api_key_prefix=token[:6])

    # Default dev/testing keys if no environment keys provided
    if not keys:
        keys["aerocast_admin_dev_token"] = UserIdentity(username="admin_dev", role=UserRole.ADMIN, api_key_prefix="admin_")
        keys["aerocast_operator_dev_token"] = UserIdentity(username="operator_dev", role=UserRole.OPERATOR, api_key_prefix="oper_")
        keys["aerocast_researcher_dev_token"] = UserIdentity(username="researcher_dev", role=UserRole.RESEARCHER, api_key_prefix="rese_")
        keys["aerocast_viewer_dev_token"] = UserIdentity(username="viewer_dev", role=UserRole.VIEWER, api_key_prefix="view_")

    return keys


def authenticate_request(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> UserIdentity:
    """FastAPI dependency to authenticate requests via X-API-Key or Bearer Token."""
    token: Optional[str] = None
    if x_api_key:
        token = x_api_key.strip()
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token:
        # Check if anonymous viewer access is permitted in dev mode
        if os.getenv("AEROCAST_ALLOW_ANONYMOUS_READ", "true").lower() in ("true", "1", "yes"):
            return UserIdentity(username="anonymous", role=UserRole.VIEWER, api_key_prefix="anon_")
        raise AuthenticationError("Missing API Key or Authorization header")

    active_keys = get_configured_api_keys()
    
    # Constant-time comparison to prevent timing attacks
    for valid_key, identity in active_keys.items():
        if secrets.compare_digest(token, valid_key):
            return identity

    raise AuthenticationError("Invalid API Key or token supplied")


def require_role(min_role: UserRole):
    """Dependency factory enforcing minimum required role in role hierarchy."""
    def _role_checker(user: UserIdentity = Depends(authenticate_request)) -> UserIdentity:
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        req_level = ROLE_HIERARCHY.get(min_role, 0)
        if user_level < req_level:
            raise AuthorizationError(
                f"Action requires minimum role {min_role.value}, but current user has {user.role.value}"
            )
        return user
    return _role_checker
