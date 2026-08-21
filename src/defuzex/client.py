"""Backward-compatible public client backed by the v4 HTTP boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .backend import (
    DEFAULT_BASE_URL,
    BackendClient,
    WireTransport,
    _validate_base_url,
    _validate_timeout,
)
from .config import resolve_api_key
from .errors import (
    AuthenticationError,
    LimitExceededError,
    PermissionDeniedError,
)
from .exceptions import (
    DefuzeAuthenticationError,
    DefuzePermissionError,
    DefuzeRateLimitError,
)

Transport = WireTransport


class DefuzeClient:
    """Compatibility client for account and public service configuration reads."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = _validate_base_url(base_url)
        self.timeout = _validate_timeout(timeout)
        resolved_key = resolve_api_key(api_key, required=False)
        self._authenticated = resolved_key is not None
        self._backend = (
            None
            if resolved_key is None
            else BackendClient(
                resolved_key,
                base_url=self.base_url,
                timeout=self.timeout,
                transport=transport,
                max_retries=0,
            )
        )

    def __repr__(self) -> str:
        return (
            f"DefuzeClient(base_url={self.base_url!r}, "
            f"authenticated={self._authenticated})"
        )

    def _read(self, path: str) -> Mapping[str, Any]:
        if self._backend is None:
            raise DefuzeAuthenticationError(
                401, "Set DEFUZEX_API_KEY or pass api_key to DefuzeClient."
            )
        try:
            return self._backend.json("GET", path)
        except AuthenticationError:
            raise DefuzeAuthenticationError(
                401, "The DefuzeX API key is invalid, expired, or revoked."
            ) from None
        except PermissionDeniedError:
            raise DefuzePermissionError(
                403, "The DefuzeX API key lacks permission for this operation."
            ) from None
        except LimitExceededError:
            raise DefuzeRateLimitError(
                429, "The DefuzeX account quota has been exhausted."
            ) from None

    def entitlements(self) -> Mapping[str, Any]:
        """Return user, key scopes, subscription, and quota information."""

        return self._read("/sdk/entitlements/")

    def strategies(self) -> Mapping[str, Any]:
        """Return the Backend-managed active Case strategy configuration."""

        return self._read("/sdk/strategies/")

    def judge_config(self) -> Mapping[str, Any]:
        """Return current public Judge upload limits and evidence types."""

        return self._read("/sdk/judge/config/")


__all__ = ["DEFAULT_BASE_URL", "DefuzeClient", "Transport"]
