"""Bind explicit local span actors without extending the frozen Evidence wire."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import ValidationError
from .public_messages import SOURCE_ACTORS


def invalid_agent_output_actor() -> ValidationError:
    """Return a value-free error for an unusable explicit final-output actor."""
    return ValidationError(
        "Agent output actor requires a completed nonempty output and public message Evidence",
        code="agent_output_actor_invalid",
    )


def validate_agent_output_actor(value: Any) -> str | None:
    """Validate an optional local declaration without inferring its truth.

    Run uses this before capture; official upload revalidates persisted metadata
    before binding existing provenance to final safe output bytes. None retains
    unknown attribution. Only the existing SOURCE_ACTORS enum is accepted;
    invalid types/values raise agent_output_actor_invalid without their repr.
    No I/O, mutation, runtime wire field or completeness upgrade is introduced.
    """
    if value is not None and (not isinstance(value, str) or value not in SOURCE_ACTORS):
        raise invalid_agent_output_actor()
    return value


def validate_attributed_output(output: Any) -> None:
    """Require a nonempty already graph-validated output for explicit attribution.

    Run checks before capture and the upload binder rechecks local persisted
    content. Null, blank strings and empty containers cannot provide a source;
    numeric zero and False remain valid. Raises the value-free actor error,
    without mutating content or making any inference about embedded speakers.
    """
    if (
        output is None
        or (isinstance(output, str) and not output.strip())
        or (isinstance(output, (Mapping, list, tuple)) and not output)
    ):
        raise invalid_agent_output_actor()


def invalid_runtime_actor() -> ValidationError:
    """Return a safe selector error without exposing captured values or IDs."""
    return ValidationError(
        "Runtime actor selectors must identify unique captured spans without conflicts",
        code="runtime_actor_invalid",
    )


def validate_runtime_actors(value: Any) -> list[dict[str, str]]:
    """Detach at most 1000 exact trace/span/actor declarations before capture.

    Run.submit owns this local-only input. None means no declarations; all
    undeclared runtime actors remain unknown. Each native list/tuple entry must
    contain only lowercase nonzero OTel trace_id (32 hex), span_id (16 hex), and
    an existing public actor enum. Duplicate selectors, including equal actors,
    raise ValidationError(runtime_actor_invalid). No capture, I/O or inference
    occurs; declarations are caller assertions, never attestations.
    """
    if value is None:
        return []
    if type(value) not in (list, tuple) or len(value) > 1000:
        raise invalid_runtime_actor()
    result, seen = [], set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {
            "trace_id",
            "span_id",
            "actor",
        }:
            raise invalid_runtime_actor()
        for field, width in (("trace_id", 32), ("span_id", 16)):
            identifier = item[field]
            if (
                not isinstance(identifier, str)
                or re.fullmatch(rf"[0-9a-f]{{{width}}}", identifier) is None
                or int(identifier, 16) == 0
            ):
                raise invalid_runtime_actor()
        actor = item["actor"]
        identity = (item["trace_id"], item["span_id"])
        if not isinstance(actor, str) or actor not in SOURCE_ACTORS or identity in seen:
            raise invalid_runtime_actor()
        seen.add(identity)
        result.append(dict(item))
    return result


def selected_span_index(
    selector: Mapping[str, str], spans: Sequence[Mapping[str, Any]]
) -> int:
    """Resolve one explicit identity after capture or final upload projection.

    Matching is exact, not by name, ancestry or message actor. Missing/dropped
    and ambiguous spans raise safe ValidationError before commit or POST. This
    pure resolver does not change capture coverage, budgets, or span contents.
    """
    matches = [
        index
        for index, span in enumerate(spans)
        if all(span.get(key) == selector[key] for key in ("trace_id", "span_id"))
    ]
    if len(matches) != 1:
        raise invalid_runtime_actor()
    return matches[0]
