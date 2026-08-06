"""Backward-compatible user service imports.

New code should import from app.services.user_service.
"""

from app.services.user_service import (
    VALID_ROLES,
    create_user,
    get_user_by_username,
    normalize_username,
    record_login,
)

__all__ = [
    "VALID_ROLES",
    "create_user",
    "get_user_by_username",
    "normalize_username",
    "record_login",
]
