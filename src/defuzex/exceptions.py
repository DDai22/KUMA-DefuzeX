"""Backward-compatible v0.2 exception names.

New code should import the stable v4 hierarchy from :mod:`defuzex.errors`.
"""

from __future__ import annotations

from typing import Any

from .errors import (
    AuthenticationError,
    DefuzeError,
    DefuzeTimeoutError,
    ServiceError,
)


class DefuzeAPIError(ServiceError):
    """The DefuzeX API returned an error response."""

    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"DefuzeX API error {status_code}: {message}",
            code="service_error",
            retryable=status_code in {408, 429, 502, 503, 504},
        )


class DefuzeAuthenticationError(DefuzeAPIError, AuthenticationError):
    """The API key is missing, invalid, expired, or revoked."""


class DefuzePermissionError(DefuzeAPIError):
    """The API key or subscription does not permit the operation."""


class DefuzeRateLimitError(DefuzeAPIError):
    """The account has exhausted its current DefuzeX quota."""


__all__ = [
    "DefuzeAPIError",
    "DefuzeAuthenticationError",
    "DefuzeError",
    "DefuzePermissionError",
    "DefuzeRateLimitError",
    "DefuzeTimeoutError",
]
