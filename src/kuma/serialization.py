"""Safe conversion of immutable public KUMA contracts to plain JSON graphs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from operator import methodcaller
from typing import Any

from ._json_values import detach_json
from .contracts import (
    CaptureComponent,
    CaptureStatus,
    Case,
    FileChange,
    FileEvidence,
    HistoryItem,
    JudgeBatchResult,
    KumaInput,
    Submission,
    TestReport,
)
from .errors import KumaError, ValidationError
from .repository.strategy_groups import (
    ResolvedStrategyGroup,
    StrategyGroup,
    StrategyGroupCatalog,
    StrategyGroupDeclaration,
)
from .repository.tool_capabilities import (
    AgentCapabilities,
    ResourceScope,
    ToolCapability,
)
from .transport._request_contract import RequestRecord


def _contract_fields(value: Any) -> Mapping[str, Any]:
    """Return declared fields for one exact immutable runtime contract.

    The public projector invokes this only for types explicitly registered in
    ``_PUBLIC_OBJECT_PROJECTORS``. It does not accept or reflect arbitrary
    dataclasses and leaves bounded detachment to the shared JSON walker.

    Args:
        value: Exact registered runtime contract instance.

    Returns:
        A temporary mapping from each declared public field name to its current
        frozen value.

    Side Effects:
        Reads dataclass fields in memory only.

    Security/Privacy:
        Registration, rather than dataclass membership alone, defines which
        typed objects may be projected.
    """
    return {item.name: getattr(value, item.name) for item in fields(value)}


_PUBLIC_OBJECT_PROJECTORS = {
    KumaInput: _contract_fields,
    FileChange: _contract_fields,
    FileEvidence: _contract_fields,
    CaptureComponent: _contract_fields,
    CaptureStatus: _contract_fields,
    Submission: _contract_fields,
    Case: _contract_fields,
    HistoryItem: _contract_fields,
    TestReport: _contract_fields,
    JudgeBatchResult: _contract_fields,
    StrategyGroupDeclaration: methodcaller("to_dict"),
    StrategyGroup: methodcaller("to_dict"),
    StrategyGroupCatalog: methodcaller("to_dict"),
    ResolvedStrategyGroup: methodcaller("to_wire"),
    ResourceScope: methodcaller("to_dict"),
    ToolCapability: methodcaller("to_dict"),
    AgentCapabilities: methodcaller("to_dict"),
    RequestRecord: methodcaller("to_dict"),
}


def _public_object_fields(value: Any) -> Mapping[str, Any] | None:
    """Project only documented public contract and error objects into JSON fields.

    The serialization boundary calls this while recursively detaching a graph.
    Exact type matching rejects subclasses and arbitrary dataclasses, preventing
    reflection of fields that KUMA has not declared public. ``KumaError`` uses
    its stable public diagnostic attributes rather than its instance state.

    Args:
        value: Current non-scalar value encountered by the bounded JSON walker.

    Returns:
        A field mapping for an exact public contract or a stable ``KumaError``;
        otherwise ``None`` so the walker applies ordinary JSON validation.

    Postconditions:
        A returned mapping contains only documented public field names. The
        source object is not mutated.

    Side Effects:
        Reads in-memory public attributes only; performs no I/O or state change.

    Security/Privacy:
        Arbitrary objects are never introspected and error causes are not read.
    """
    projector = _PUBLIC_OBJECT_PROJECTORS.get(type(value))
    if projector is not None:
        return projector(value)
    if isinstance(value, KumaError):
        return {
            "code": value.code,
            "message": str(value),
            "request_id": value.request_id,
            "retryable": value.retryable,
            "details": value.details,
        }
    return None


def to_json(value: Any) -> Any:
    """Detach a public KUMA contract or JSON value into a plain JSON graph.

    Use this function before passing a frozen SDK value to ``json.dumps`` or a
    third-party JSON encoder. It supports the public contract classes exported
    by :mod:`kuma`, nested :class:`KumaError` values in batch results, and the
    same finite JSON scalars/mappings/sequences accepted by Input and
    Submission fields.

    Args:
        value: A public KUMA contract object or finite JSON-compatible value.
            Mappings and arrays may contain at most 256 container levels. A
            shared acyclic child is accepted; cycles and arbitrary objects are
            rejected.

    Returns:
        A detached graph made only of ``dict``, ``list``, ``str``, ``int``,
        finite ``float``, ``bool``, and ``None``. The function returns a graph,
        not encoded JSON text; call ``json.dumps(to_json(value))`` to encode it.

    Raises:
        ValidationError: If ``value`` is cyclic, too deep, non-finite, contains
            an unsupported value, or fails while a custom mapping is read. The
            stable error code is ``output_invalid``.

    Preconditions:
        Only already-public SDK contracts should be supplied as typed objects.
        Private service objects are outside this API and are rejected.

    Postconditions:
        The source contract remains immutable. Every returned container is a
        new mutable copy, so changing it cannot modify Run history or reports.
        Successful output can be encoded with ``allow_nan=False``.

    Side Effects:
        Iterates values in memory only. It performs no filesystem access,
        Evidence capture, network request, model call, billing, or Run state
        transition.

    Security/Privacy:
        Only documented public fields are projected from typed objects.
        Failures contain no source key, value, object representation, or raw
        exception text. This function preserves public values; it is not a
        redaction substitute for an application that adds secrets to output.
    """
    try:
        return detach_json(value, object_fields=_public_object_fields)
    except Exception:
        raise ValidationError(
            "value must be a finite public KUMA contract or JSON value",
            code="output_invalid",
        ) from None


__all__ = ["to_json"]
