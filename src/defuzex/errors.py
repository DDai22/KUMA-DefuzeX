"""Stable error types for the DefuzeX v4 public API.

Exception messages intentionally exclude ``details`` so diagnostic payloads cannot
accidentally disclose credentials when an exception is printed or logged.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


class DefuzeError(Exception):
    """Base exception raised by the DefuzeX SDK."""

    default_code = "defuzex_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        request_id: str | None = None,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.request_id = request_id
        self.retryable = retryable
        self.details = MappingProxyType(dict(details or {}))
        super().__init__(message)


class ConfigurationError(DefuzeError):
    default_code = "config_invalid"


class AuthenticationError(DefuzeError):
    default_code = "auth_invalid"


class PermissionDeniedError(DefuzeError):
    default_code = "forbidden"


class ValidationError(DefuzeError):
    default_code = "validation_error"


class SensitiveDataError(ValidationError):
    default_code = "sensitive_data_blocked"


class DockerRequiredError(ConfigurationError):
    default_code = "docker_required"


class RunAlreadyActiveError(DefuzeError):
    default_code = "run_already_active"


class ProviderError(DefuzeError):
    default_code = "provider_failed"


class InputProtocolError(DefuzeError):
    default_code = "invalid_run_state"


class EvidenceCaptureError(DefuzeError):
    default_code = "evidence_capture_failed"


class LimitExceededError(ValidationError):
    default_code = "limit_exceeded"


class CaseIntegrityError(ValidationError):
    default_code = "invalid_case_integrity"


class RepoStateMismatchError(ValidationError):
    default_code = "repo_state_mismatch"


class ServiceBusyError(DefuzeError):
    default_code = "service_busy"


class DefuzeTimeoutError(DefuzeError):
    default_code = "timeout"


class ServiceError(DefuzeError):
    default_code = "service_error"


__all__ = [
    "AuthenticationError",
    "CaseIntegrityError",
    "ConfigurationError",
    "DefuzeError",
    "DefuzeTimeoutError",
    "DockerRequiredError",
    "EvidenceCaptureError",
    "InputProtocolError",
    "LimitExceededError",
    "PermissionDeniedError",
    "ProviderError",
    "RepoStateMismatchError",
    "RunAlreadyActiveError",
    "SensitiveDataError",
    "ServiceBusyError",
    "ServiceError",
    "ValidationError",
]
