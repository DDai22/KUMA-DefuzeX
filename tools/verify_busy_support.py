"""Verify busy support headers offline against source or an installed SDK.

Run with PYTHONPATH=src for a checkout, or python -I with an installed wheel.
Only urllib's network boundary is mocked; SDK decoding/mapping/polling are real.
No account, model, service credit or private test package is needed.
"""

import json
import os
import tempfile
import unittest
from email.message import Message
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from kuma.errors import AuthenticationError, ServiceBusyError
from kuma.transport.backend import BackendClient
from kuma.transport.operations import PendingOperationStore, await_operation

REQUEST_ID = "0123456789abcdef0123456789abcdef"
BUSY = "Service is busy. Please try again later."


class BusySupportTests(unittest.TestCase):
    """Check closed metadata and unchanged official error/retry boundaries."""

    def test_http_headers(self):
        """Decode real HTTPError streams without executing any network calls."""
        for values in (
            ["SB000"],
            ["SB001"],
            ["SB002"],
            ["SB003"],
            [],
            ["private"],
            ["SB001", "SB001"],
        ):
            for identifier in (REQUEST_ID, "/private/path", None):
                with self.subTest(values=values, identifier=identifier):
                    headers = Message()
                    for value in values:
                        headers["X-KUMA-Support-Code"] = value
                    if identifier is not None:
                        headers["X-Request-ID"] = identifier
                    body = json.dumps(
                        {
                            "error": {
                                "code": "service_busy",
                                "retryable": True,
                                "message": "PRIVATE_BODY model_timeout",
                            }
                        }
                    ).encode()
                    failure = HTTPError(
                        "https://example.test/sdk/v2/judge/",
                        503,
                        "private",
                        headers,
                        BytesIO(body),
                    )
                    client = BackendClient(
                        "dfx_synthetic", base_url="https://example.test", max_retries=2
                    )
                    with (
                        patch(
                            "kuma.transport.backend.urlopen", side_effect=failure
                        ) as opened,
                        self.assertRaises(ServiceBusyError) as caught,
                    ):
                        client.json(
                            "POST",
                            "/sdk/v2/judge/",
                            {},
                            idempotency_key="synthetic",
                        )
                    support = (
                        values[0]
                        if len(values) == 1
                        and values[0] in {"SB000", "SB001", "SB002", "SB003"}
                        else None
                    )
                    expected = BUSY + (f" Support code: {support}." if support else "")
                    expected += (
                        f" Support ID: {REQUEST_ID}" if identifier == REQUEST_ID else ""
                    )
                    self.assertEqual(str(caught.exception), expected)
                    self.assertEqual(caught.exception.support_code, support)
                    self.assertTrue(caught.exception.retryable)
                    opened.assert_called_once()

    def test_terminal_poll(self):
        """Carry a real decoded HTTP 200 failure's header outside JSON keys."""
        with tempfile.TemporaryDirectory() as directory:
            client = BackendClient("dfx_synthetic", base_url="https://example.test")
            response = BytesIO(
                json.dumps(
                    {
                        "operation_id": "op-test",
                        "status": "failed",
                        "error": {"code": "service_busy", "retryable": False},
                    }
                ).encode()
            )
            response.status = 200
            response.headers = {
                "X-KUMA-Support-Code": "SB003",
                "X-Request-ID": REQUEST_ID,
            }
            store = PendingOperationStore(
                Path(directory) / "pending.json",
                operation_type="judgment",
                base_url=client.base_url,
            )
            with (
                patch(
                    "kuma.transport.backend.urlopen", return_value=response
                ) as opened,
                self.assertRaises(ServiceBusyError) as caught,
            ):
                await_operation(
                    client,
                    store,
                    key_factory=lambda: "synthetic",
                    start=lambda key, deadline: {
                        "operation_id": "op-test",
                        "status": "queued",
                        "poll_after_ms": 100,
                    },
                    wait_timeout=2,
                )
            self.assertEqual(
                str(caught.exception),
                BUSY + f" Support code: SB003. Support ID: {REQUEST_ID}",
            )
            self.assertFalse(caught.exception.retryable)
            opened.assert_called_once()
            self.assertEqual(opened.call_args.args[0].get_method(), "GET")

    def test_nonbusy_and_custom_errors(self):
        """Ignore unsolicited support headers and preserve custom formatting."""
        headers = Message()
        headers["X-KUMA-Support-Code"] = "SB001"
        failure = HTTPError(
            "https://example.test/sdk/config/",
            401,
            "private",
            headers,
            BytesIO(b'{"error":{"code":"invalid_api_key","retryable":false}}'),
        )
        client = BackendClient("dfx_synthetic", base_url="https://example.test")
        with (
            patch("kuma.transport.backend.urlopen", side_effect=failure),
            self.assertRaises(AuthenticationError) as caught,
        ):
            client.json("GET", "/sdk/config/")
        self.assertIsNone(caught.exception.support_code)
        self.assertNotIn("Support", str(caught.exception))
        self.assertEqual(
            str(ServiceBusyError("custom", support_code="SB001")), "custom"
        )


if __name__ == "__main__":
    os.environ["KUMA_DISABLE_UPDATE_CHECK"] = "1"
    unittest.main()
