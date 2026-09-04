"""Stable internal facade for official asynchronous request recovery."""

from ._request_contract import (
    REQUEST_RECORD_SCHEMA,
    REQUEST_RECOVERY_SCHEMA,
    RequestRecord,
    StoredRequest,
    backend_identity,
    canonical_request_sha256,
    new_client_request_id,
    validate_recovery_response,
)
from ._request_query import (
    find_active_request,
    list_request_records,
    load_request_record,
    store_for_existing,
)
from ._request_store import RequestOperationStore

_StoredRequest = StoredRequest

__all__ = [
    "REQUEST_RECORD_SCHEMA",
    "REQUEST_RECOVERY_SCHEMA",
    "RequestOperationStore",
    "RequestRecord",
    "backend_identity",
    "canonical_request_sha256",
    "find_active_request",
    "list_request_records",
    "load_request_record",
    "new_client_request_id",
    "store_for_existing",
    "validate_recovery_response",
]
