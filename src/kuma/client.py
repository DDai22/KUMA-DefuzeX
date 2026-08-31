"""Public account and service-configuration client for the v4 HTTP boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import resolve_api_key
from .errors import (
    AuthenticationError,
    LimitExceededError,
    PermissionDeniedError,
)
from .exceptions import (
    KumaAuthenticationError,
    KumaPermissionError,
    KumaRateLimitError,
)
from .transport.backend import (
    DEFAULT_BASE_URL,
    BackendClient,
    WireTransport,
    _validate_base_url,
    _validate_timeout,
)

Transport = WireTransport


class KumaClient:
    """Read account and public service configuration without creating a Run.

    Args:
        api_key: Optional ``dfx_`` credential. ``None`` resolves
            ``KUMA_API_KEY`` and then the user credential file. Construction may
            remain unauthenticated, but read methods then raise
            ``KumaAuthenticationError``.
        base_url: Public Backend API base URL. Remote URLs require HTTPS;
            loopback HTTP is accepted for local integration.
        timeout: Positive finite timeout in seconds for each GET request.
        transport: Optional test/integration transport implementing the public
            wire callable contract. Ordinary users should leave it as ``None``.

    Raises:
        ConfigurationError: The URL, timeout, or resolved credential is invalid.

    The client never contacts MCP, model providers, or databases directly.
    """

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
            f"KumaClient(base_url={self.base_url!r}, "
            f"authenticated={self._authenticated})"
        )

    def _read(self, path: str) -> Mapping[str, Any]:
        if self._backend is None:
            raise KumaAuthenticationError(
                401, "Set KUMA_API_KEY or pass api_key to KumaClient."
            )
        try:
            return self._backend.json("GET", path)
        except AuthenticationError:
            raise KumaAuthenticationError(
                401, "The KUMA API key is invalid, expired, or revoked."
            ) from None
        except PermissionDeniedError:
            raise KumaPermissionError(
                403, "The KUMA API key lacks permission for this operation."
            ) from None
        except LimitExceededError:
            raise KumaRateLimitError(
                429, "The KUMA account quota has been exhausted."
            ) from None

    def entitlements(self) -> Mapping[str, Any]:
        """Return public user, key-scope, subscription, and quota information.

        Raises ``KumaAuthenticationError``, ``KumaPermissionError``, or
        ``KumaRateLimitError`` for the corresponding public HTTP boundary.
        """

        return self._read("/sdk/entitlements/")

    def strategies(self) -> Mapping[str, Any]:
        """Return the Backend-managed public active Case strategy catalog.

        This is an explicit discovery read; Case generation does not use it as a
        client-side availability precheck.
        """

        return self._read("/sdk/strategies/")

    def judge_config(self) -> Mapping[str, Any]:
        """Return current public Judge upload limits and accepted Evidence types."""

        return self._read("/sdk/judge/config/")


__all__ = ["DEFAULT_BASE_URL", "KumaClient", "Transport"]
