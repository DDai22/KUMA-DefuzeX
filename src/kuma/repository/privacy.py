"""High-confidence sensitive-data checks used immediately before upload."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._json_values import detach_json
from ..errors import SensitiveDataError

REDACTED = "[REDACTED]"
_CREDENTIAL_NAME = (
    r"(?:[A-Za-z][A-Za-z0-9_.-]*[_.-])?"
    r"(?:api[_-]?key|(?:access|auth|refresh|tampered|session)[_-]?token|token|"
    r"client[_-]secret|secret[_-]access[_-]key|private[_-]key|"
    r"credential(?:s)?|password|passwd|secret|auth(?:orization)?|(?:set[_-]?)?cookie)"
)
_CREDENTIAL_KEY = re.compile(rf"(?i)^{_CREDENTIAL_NAME}$")
_BRACED_ENV_REFERENCE = re.compile(r"\$\{[A-Z_][A-Z0-9_]*\}")
_SOURCE_REFERENCE = re.compile(
    r"""(?mx)^[\t ]*(?:
    [A-Za-z_][A-Za-z0-9_]*[\t ]*=[\t ]*
      (?P<environment>os\.environ\.get\([\t ]*
        (?P<quote>["'])[A-Z_][A-Z0-9_]*(?P=quote)
        (?:[\t ]*,[\t ]*(?:""|''))?[\t ]*\))
    |password[\t ]*=[\t ]*(?P<keyword>db_password),
    |private_key[\t ]*=[\t ]*(?P<path>Path\(tmpdir\)[\t ]*/[\t ]*"private\.pem")
    )[\t ]*$"""
)
_PEM_SOURCE_TEMPLATE = re.compile(
    r"""(?mx)^[\t ]*pem[\t ]*=[\t ]*\(
    "(?P<header>-----BEGIN\ PRIVATE\ KEY-----)\\n"[\t ]*\+[\t ]*
    "\\n"\.join\(lines\)[\t ]*\+[\t ]*
    "\\n-----END\ PRIVATE\ KEY-----\\n"\)[\t ]*$"""
)
_ASSIGNMENT = re.compile(
    rf"(?i)(?<![\w])(?P<label>{_CREDENTIAL_NAME}[\"']?\s*[:=]\s*(?:\*\*\s*)?)"
    r"(?P<value>(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
    r"\$\{[^\s,;]*|[^\s,;}])+)"
)
_AUTHORIZATION_HEADER = re.compile(
    r"(?im)\bauthorization[\"']?[ \t]*:[ \t]*(?=(?P<value>[^\r\n]*))"
)
_COOKIE_HEADER = re.compile(r"(?im)\b(?:set-)?cookie\s*:[^\r\n]*")
_PLACEHOLDER_AUTH_VALUE = re.compile(
    r"(?ix)^(?:"
    r"<your[-_](?:access[-_])?token>|"
    r"\$(?:[A-Z][A-Z0-9_]*|\{[A-Z][A-Z0-9_]*\})|"
    r"YOUR_[A-Z0-9_]+|"
    r"TOKEN|ACCESS_TOKEN|API_KEY|"
    r"\.\.\."
    r")$"
)
_RFC7617_BASIC_SAMPLE = "YWxhZGRpbjpvcGVuc2VzYW1l"

_SENSITIVE_BASENAMES = frozenset(
    {
        ".env",
        ".npmrc",
        ".pypirc",
        "credentials",
        "credentials.json",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
    }
)
_SENSITIVE_SUFFIXES = frozenset({".key", ".p12", ".pfx", ".pem"})
_TEXT_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("cookie", re.compile(r"(?i)\b(?:set-)?cookie\s*:\s*[^\s=;]+=[^\s;]{6,}")),
    ("authorization_bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "github_token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b"),
    ),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "sk_api_key",
        re.compile(r"\bsk-(?:(?:proj|ant-api03)-)?[A-Za-z0-9_-]{12,}\b"),
    ),
    # Unkey issues 32-byte no-dot keys; retain legacy dot-separated credentials.
    (
        "kuma_key",
        re.compile(
            r"\bdfx_(?:[A-Za-z0-9_-]{6,}\.[A-Za-z0-9._-]{12,}\b|"
            r"[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-]))"
        ),
    ),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9+/_.=-]{16,}"
        ),
    ),
)
PRIVATE_DATA_FIELDS = frozenset(
    {
        "answer_key",
        "deepseek_key",
        "expected_answer",
        "expected_output",
        "hidden_answer",
        "hidden_inputs",
        "internal_labels",
        "mcp_address",
        "mcp_url",
        "model_config",
        "private_prompt",
        "private_rubric",
        "provider_key",
        "system_prompt",
    }
)


@dataclass(frozen=True, slots=True)
class SensitiveFinding:
    """Identify a sensitive-data category without retaining the matched value.

    Attributes:
        kind: Stable category such as credential file, API token, or private field.
        location: Caller-supplied safe component/path label, not secret content.
    """

    kind: str
    location: str

    @property
    def reason(self) -> str:
        """Return the stable public reason code for this sensitive-data finding."""
        return f"sensitive_{self.kind}:{self.location}"


def scan_sensitive_path(
    path: str | Path, *, location: str = "file"
) -> tuple[SensitiveFinding, ...]:
    """Return a finding when a path suggests credentials or private data."""
    candidate = Path(path)
    basename = candidate.name.casefold()
    if (
        basename in _SENSITIVE_BASENAMES
        or basename.startswith(".env.")
        or candidate.suffix.casefold() in _SENSITIVE_SUFFIXES
    ):
        return (SensitiveFinding("credential_file", location),)
    return ()


def scan_sensitive_text(text: str, *, location: str) -> tuple[SensitiveFinding, ...]:
    """Scan bounded text for credential and private-data signatures."""
    safe_authorization_spans = _safe_authorization_spans(text)
    source_spans = _source_reference_spans(text)
    pem_spans = tuple(m.span("header") for m in _PEM_SOURCE_TEMPLATE.finditer(text))
    findings = []
    for kind, pattern in _TEXT_PATTERNS:
        matches = pattern.finditer(text)
        if kind in {"private_key", "credential_assignment"}:
            matches = (
                match
                for match in matches
                if not _inside_spans(
                    match.span()
                    if kind == "private_key"
                    else (match.end() - 1, match.end()),
                    pem_spans if kind == "private_key" else source_spans,
                )
            )
        if kind == "authorization_bearer":
            matches = (
                match
                for match in matches
                if not _inside_spans(match.span(), safe_authorization_spans)
            )
        if next(matches, None) is not None:
            findings.append(SensitiveFinding(kind, location))
    if any(
        _authorization_match_is_secret(match)
        for match in _AUTHORIZATION_HEADER.finditer(text)
    ):
        findings.append(SensitiveFinding("authorization", location))
    if any(
        _assignment_is_secret(match)
        and not _inside_spans(match.span(), safe_authorization_spans)
        and not _inside_spans(match.span("value"), source_spans)
        for match in _ASSIGNMENT.finditer(text)
    ):
        findings.append(SensitiveFinding("credential_assignment", location))
    return tuple(findings)


def _source_reference_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Locate only closed, non-executed source-reference RHS forms.

    The scanner and redactor share this recognition. Whole standalone statements
    must match; quoted JSON values, comments, operators, nonempty defaults and
    arbitrary calls/names are not exemptions. Only the RHS is exempted from the
    assignment heuristic; independent credential signatures still inspect it.
    No imports, environment reads, parsing execution or filesystem access occur.
    The keyword and Path forms intentionally cover only the documented examples.
    """
    return tuple(
        match.span(name)
        for match in _SOURCE_REFERENCE.finditer(text)
        if match.end() - match.start() <= 4096
        for name in ("environment", "keyword", "path")
        if match[name] is not None
    )


def _assignment_is_secret(match: re.Match[str]) -> bool:
    """Keep machine assignments strict while recognizing bounded prose contexts.

    Detection and replacement share these rules. Exact documentation placeholders
    carry no credential value. Only unquoted colon labels with bounded glossary
    syntax or existing academic, employment and no-auth wording qualify as prose. Passwords,
    short real secrets, equals assignments and quoted values remain sensitive;
    independent known-token/private-key signatures still scan the whole text.
    Whole braced environment references and exact your_password/ellipsis
    placeholders are syntax only, never resolved. The
    assignment matcher consumes adjacent scalar fragments together so a valid
    reference cannot exempt an attached literal, expansion operator or suffix.
    """
    value = match["value"]
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        value = value[1:-1]
    if _BRACED_ENV_REFERENCE.fullmatch(value):
        return False
    if value in {"", REDACTED, "your_password", "..."} or re.fullmatch(
        r"(?:<[A-Za-z][A-Za-z0-9_-]*>|\$[A-Z_][A-Z0-9_]*|YOUR_[A-Z_]+|sk-[.…]+)`?",
        value,
    ):
        return False
    return not _assignment_is_prose(match)


def _assignment_is_prose(match: re.Match[str]) -> bool:
    """Share bounded glossary/legacy prose recognition without exempting tails."""
    if "=" in match["label"] or match["value"].startswith(("'", '"')):
        return False
    if _glossary_prose(match):
        return True
    value = match["value"]
    label = match["label"].split(":", 1)[0].casefold()
    tail = match.string[match.start("value") :].splitlines()[0]
    contexts = {
        "credentials": r"(?:PhD|MSc|BSc|(?:academic|professional) qualifications|use a NACES-member evaluator)(?=[ \t]|$)",
        "authorization": r"Statutory right-to-work checks(?=[ \t]|$)",
        "auth": r"(?:None required|Authorized)(?=[ \t]|$)",
        "token": r"the unit of text(?=[ \t]|$)",
    }
    if (
        label in {"auth", "authorization"}
        and re.search(r"(?i)\bwork[ \t]+$", match.string[: match.start()])
        and value.casefold()
        in {
            "permitted",
            "authorized",
            "required",
            "prohibited",
        }
    ):
        return True
    pattern = contexts.get(label)
    return pattern is not None and re.match(pattern, tail, re.IGNORECASE) is not None


def _glossary_prose(match: re.Match[str]) -> bool:
    """Recognize bounded explanatory colon prose, never a machine secret slot.

    Shared by text scanning and redaction through assignment/header handling.
    A token glossary value must start with an article and contain at least five
    ordinary words. Authorization additionally needs a compound prose heading
    joined by 'and' or 'or'; a bare Authorization header remains strict. Quotes,
    equals signs, code delimiters and non-prose characters do not qualify.
    JSON credential keys are validated separately and never use this exemption.

    Returns:
        Whether the first matched scalar is part of that explanatory sentence.
        Only that scalar is exempted; independent signatures and subsequent
        assignments still scan the whole body. This is syntax classification,
        not proof that arbitrary natural-language content contains no secrets.

    Side Effects:
        None; no external reads, execution or mutation.
    """
    label = match["label"].split(":", 1)[0].casefold()
    if label not in {"token", "authorization"}:
        return False
    tail = match.string[match.start("value") :].splitlines()[0]
    if len(tail) > 4096 or re.fullmatch(r"[A-Za-z\s.,()'\-]+", tail) is None:
        return False
    words = re.findall(r"[A-Za-z]+", tail)
    if len(words) < 5 or words[0].casefold() not in {"a", "an", "the"}:
        return False
    if label == "token":
        return True
    prefix = match.string[: match.start()].rsplit("\n", 1)[-1]
    return (
        re.fullmatch(
            r"(?i)[ \t]*(?:[-*][ \t]+)?(?:\*\*)?"
            r"[A-Za-z]+(?:[ \t]+[A-Za-z]+)*[ \t]+(?:and|or)[ \t]+",
            prefix,
        )
        is not None
    )


def _authorization_match_is_secret(match: re.Match[str]) -> bool:
    """Reject headers without a complete recognized safe value or prose form."""
    return _safe_authorization_end(match) is None


def _authorization_value_is_safe(value: str) -> bool:
    """Accept only complete Bearer/Basic placeholders or the public RFC sample."""
    if any(
        pattern.search(value)
        for kind, pattern in _TEXT_PATTERNS
        if kind != "authorization_bearer"
    ):
        return False
    example = re.fullmatch(r"(?i)(bearer|basic)[ \t]+(\S+)", value.strip())
    if example is None:
        return False
    scheme, credential = example.groups()
    return bool(_PLACEHOLDER_AUTH_VALUE.fullmatch(credential)) or (
        scheme.casefold() == "basic" and credential == _RFC7617_BASIC_SAMPLE
    )


def _safe_authorization_end(match: re.Match[str]) -> int | None:
    """Return the end of a proven safe header, leaving surrounding text untrusted.

    The header pattern looks ahead through the line without consuming it, so a
    second header on that line is checked independently. Quotes/backticks must
    be adjacent and paired exactly, including JSON-escaped double quotes. Bare
    prose is limited to the two issue examples and existing employment wording;
    arbitrary suffixes and incomplete delimiters fail closed.
    """
    value = match["value"]
    prefix = match.string[: match.start()]
    delimiter = prefix[-1:]
    if delimiter in {"'", '"', "`"}:
        if prefix.endswith('\\"'):
            delimiter = '\\"'
        end = value.find(delimiter)
        if end < 0 or not _authorization_value_is_safe(value[:end]):
            return None
        tail = value[end + len(delimiter) :]
        if tail and not tail[0].isspace():
            return None
        return match.start("value") + end + len(delimiter)
    if value.strip() == REDACTED or _authorization_value_is_safe(value):
        return match.end("value")
    line_prefix = prefix.rsplit("\n", 1)[-1].strip()
    documentation = re.fullmatch(
        r"(?i)(?P<header>basic[ \t]+"
        + _RFC7617_BASIC_SAMPLE
        + r")[ \t]+\(RFC 7617 sample\)[ \t]*",
        value,
    )
    if (
        line_prefix == "Example:"
        and documentation
        and _authorization_value_is_safe(documentation["header"])
    ):
        return match.start("value") + documentation.end("header")
    documentation = re.fullmatch(
        r"(?i)(?P<header>bearer[ \t]+\S+)[ \t]+before calling\.[ \t]*", value
    )
    if (
        line_prefix == "Set the header to"
        and documentation
        and _authorization_value_is_safe(documentation["header"])
    ):
        return match.start("value") + documentation.end("header")
    assignment = _ASSIGNMENT.match(match.string, match.start())
    if assignment and _assignment_is_prose(assignment):
        return assignment.end()
    return None


def _safe_authorization_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Locate complete safe headers so generic token rules preserve examples."""
    return tuple(
        (match.start(), end)
        for match in _AUTHORIZATION_HEADER.finditer(text)
        if (end := _safe_authorization_end(match)) is not None
    )


def _redact_authorization_headers(text: str) -> str:
    """Remove every non-exempt header through the line end, for all schemes."""
    pieces = []
    offset = 0
    for match in _AUTHORIZATION_HEADER.finditer(text):
        if match.start() < offset or not _authorization_match_is_secret(match):
            continue
        pieces.extend((text[offset : match.start()], REDACTED))
        offset = match.end("value")
    pieces.append(text[offset:])
    return "".join(pieces)


def _inside_spans(
    span: tuple[int, int], containers: tuple[tuple[int, int], ...]
) -> bool:
    """Require a whole match to belong to a previously validated safe header."""
    return any(start <= span[0] and span[1] <= end for start, end in containers)


def redact_sensitive_text(text: str) -> str:
    """Return a safe text copy, replacing recognized credentials explicitly.

    Args:
        text: Already bounded text owned by the Evidence projection caller.

    Returns:
        Unchanged safe text or text with literal ``[REDACTED]`` markers. Any
        private-key BEGIN marker outside the closed source template omits the
        entire text, including incomplete PEM blocks; headers are removed rather than leaving
        unsafe cookie tails. No claim of detecting unknown secrets is made.

    Postconditions:
        Reapplying this function is idempotent. Caller input is never mutated.
        No matched values are retained in metadata, exceptions, or logs.

    Side Effects:
        None. Callers must recompute digests and mark changed Evidence partial;
        this function must not be applied indiscriminately to protocol IDs.
    """
    pem_spans = tuple(m.span("header") for m in _PEM_SOURCE_TEMPLATE.finditer(text))
    if any(
        not _inside_spans(m.span(), pem_spans)
        for m in _TEXT_PATTERNS[0][1].finditer(text)
    ):
        return REDACTED
    source_spans = _source_reference_spans(text)
    for match in _ASSIGNMENT.finditer(text):
        if _inside_spans(match.span("value"), source_spans):
            continue
        scalar = match["value"]
        if scalar.startswith(("'", '"')) and (
            len(scalar) == 1 or scalar[-1] != scalar[0]
        ):
            return REDACTED
    result = _redact_authorization_headers(text)
    safe_authorization_spans = _safe_authorization_spans(result)
    source_spans = _source_reference_spans(result)
    bearer_pattern = dict(_TEXT_PATTERNS)["authorization_bearer"]
    result = bearer_pattern.sub(
        lambda match: (
            match[0]
            if _inside_spans(match.span(), safe_authorization_spans)
            else REDACTED
        ),
        result,
    )
    result = _COOKIE_HEADER.sub(REDACTED, result)

    safe_authorization_spans = _safe_authorization_spans(result)

    def replace_assignment(match: re.Match[str]) -> str:
        """Retain an assignment label but never its sensitive scalar value."""
        if (
            not _assignment_is_secret(match)
            or _inside_spans(match.span("value"), source_spans)
            or _inside_spans(match.span(), safe_authorization_spans)
        ):
            return match[0]
        return match["label"] + '"' + REDACTED + '"'

    result = _ASSIGNMENT.sub(replace_assignment, result)
    for kind, pattern in _TEXT_PATTERNS:
        if kind not in {
            "private_key",
            "cookie",
            "credential_assignment",
            "authorization_bearer",
        }:
            result = pattern.sub(REDACTED, result)
    return result


def redact_sensitive_json(value: Any) -> tuple[Any, bool]:
    """Detach and sanitize a payload graph without altering its original.

    Args:
        value: Finite, acyclic JSON content, not an envelope containing protocol
            IDs. The canonical JSON depth/type validation runs before traversal.

    Returns:
        Detached JSON plus whether any content was removed/replaced. Credential
        values use the literal marker; secret-bearing keys are omitted, never
        renamed to fabricated keys. Numeric token usage and ordinary words stay.
        JSON encoded inside a string is sanitized but remains a string.

    Raises:
        JsonStructureError: The canonical graph validator rejects invalid input.

    Postconditions:
        Safe inputs retain their content and types. Reapplying redaction does
        not change the result. No original values are exposed in diagnostics.

    Side Effects:
        No filesystem or network access. The caller owns byte limits, hashes,
        association checks and schema-specific loss accounting.
    """
    return _redact_graph(detach_json(value), 0)


def _credential_value(key: str, value: Any, *, containers: bool = False) -> bool:
    """Match credential values without mistaking JSON Schema declarations for data.

    Ordinary validation scans string values recursively, preserving previously
    supported schema property objects. Outbound Evidence redaction alone may
    conservatively replace whole credential-labelled containers via ``containers``.
    Numeric usage and exact markers are never treated as credential payloads.
    Complete braced environment-reference scalars are also syntax-only markers;
    no environment access or interpolation occurs. Prefix/suffix/encoded forms
    and container values retain the existing sensitive-value behavior.
    """
    normalized = "_".join(
        part for part in re.split(r"[^a-z0-9]+", key.casefold()) if part
    )
    return bool(_CREDENTIAL_KEY.fullmatch(normalized)) and (
        (containers and isinstance(value, (dict, list)))
        or (
            isinstance(value, str)
            and value not in {"", REDACTED}
            and _BRACED_ENV_REFERENCE.fullmatch(value) is None
        )
    )


def _redact_mapping(value: dict[str, Any], depth: int) -> tuple[dict[str, Any], bool]:
    """Copy JSON fields, dropping secret keys rather than inventing replacements."""
    result = {}
    changed = False
    for key, child in value.items():
        if redact_sensitive_text(key) != key:
            changed = True
            continue
        if _credential_value(key, child, containers=True):
            result[key] = REDACTED
            changed = True
        else:
            result[key], child_changed = _redact_graph(child, depth)
            changed |= child_changed
    return result, changed


def _redact_string(value: str, depth: int) -> tuple[str, bool]:
    """Preserve string type while inspecting at most eight nested JSON encodings.

    The outer graph is already validated. Failed decoding falls back to text
    rules; exceeding the decoder bound omits the complete scalar. Unchanged
    encoded strings preserve original whitespace and ordering exactly.
    """
    if value.lstrip().startswith(("{", "[", '"')) and value != REDACTED:
        try:
            decoded = detach_json(json.loads(value, object_pairs_hook=_unique_fields))
        except (ValueError, TypeError, RecursionError):
            pass
        else:
            if depth >= 8:
                return REDACTED, True
            safe, changed = _redact_graph(decoded, depth + 1)
            if changed:
                return json.dumps(safe, ensure_ascii=True, separators=(",", ":")), True
            return value, False
    safe = redact_sensitive_text(value)
    return safe, safe != value


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys so decoding cannot hide a sensitive occurrence."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("ambiguous JSON object")
        result[key] = value
    return result


def _redact_graph(value: Any, depth: int) -> tuple[Any, bool]:
    """Traverse a detached graph; depth counts encoded strings, not containers."""
    if isinstance(value, dict):
        return _redact_mapping(value, depth)
    if isinstance(value, list):
        children = [_redact_graph(child, depth) for child in value]
        return [safe for safe, _ in children], any(changed for _, changed in children)
    if isinstance(value, str):
        return _redact_string(value, depth)
    return value, False


def _decoded_container(text: str, encoded_depth: int) -> Any:
    """Decode a bounded nested JSON container for scanning, never source code.

    Return None when the eight-layer bound, syntax, duplicate keys or canonical
    graph limits reject decoding. The caller must mark an uninspected container
    at the budget as validation_failed; raw text scanning alone cannot discharge
    that boundary. No values are included in errors or logs.
    """
    if encoded_depth >= 8 or not text.lstrip().startswith(("{", "[")):
        return None
    try:
        return detach_json(json.loads(text, object_pairs_hook=_unique_fields))
    except (ValueError, TypeError, RecursionError):
        return None


def scan_sensitive_json(value: Any, *, location: str) -> tuple[SensitiveFinding, ...]:
    """Scan JSON values and bounded encoded containers without treating keys as code.

    Upload callers may supply plain graphs or serialized JSON. Valid containers
    are decoded with duplicate-key rejection; at most eight encoded layers are
    traversed. Beyond that budget, container-shaped strings produce a value-free
    validation_failed finding, even without a visible credential. Raw scanning
    cannot prove escaped fields safe. The exact redaction marker is not a JSON
    container. Malformed strings within budget retain raw text scanning.
    Credential-labelled values are checked before source-reference recognition.
    No caller objects are changed, source evaluated, or values retained in findings.
    """
    findings: list[SensitiveFinding] = []

    def visit(item: Any, encoded_depth: int = 0) -> None:
        """Visit nested JSON values while applying the sensitive-data scanner."""
        if isinstance(item, Mapping):
            for key, child in item.items():
                if _credential_value(str(key), child):
                    findings.append(SensitiveFinding("credential_field", location))
                findings.extend(scan_sensitive_text(str(key), location=location))
                visit(child, encoded_depth)
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            for child in item:
                visit(child, encoded_depth)
        elif isinstance(item, str):
            if (
                encoded_depth >= 8
                and item != REDACTED
                and item.lstrip().startswith(("{", "["))
            ):
                findings.append(SensitiveFinding("validation_failed", location))
                return
            decoded = _decoded_container(item, encoded_depth)
            if decoded is not None:
                visit(decoded, encoded_depth + 1)
                return
            findings.extend(scan_sensitive_text(item, location=location))

    visit(value)
    return tuple(findings)


def contains_private_data(value: Any, *, extra_fields: Sequence[str] = ()) -> bool:
    """Detect protocol fields that must not cross a public SDK response."""

    prohibited = PRIVATE_DATA_FIELDS | {field.casefold() for field in extra_fields}

    def visit(item: Any) -> bool:
        """Visit nested JSON values while applying the sensitive-data scanner."""
        if isinstance(item, Mapping):
            if {str(key).casefold() for key in item} & prohibited:
                return True
            return any(visit(child) for child in item.values())
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            return any(visit(child) for child in item)
        return False

    return visit(value)


def enforce_sensitive_policy(
    findings: Sequence[SensitiveFinding],
    *,
    allow_sensitive: bool,
) -> None:
    """Raise before transport when findings are not explicitly allowed."""
    if not findings or allow_sensitive:
        return
    reasons = tuple(dict.fromkeys(item.reason for item in findings))
    raise SensitiveDataError(
        "Sensitive data was detected; remove it or explicitly set allow_sensitive=True",
        details={"reasons": reasons},
    )


__all__ = [
    "SensitiveFinding",
    "contains_private_data",
    "enforce_sensitive_policy",
    "redact_sensitive_json",
    "redact_sensitive_text",
    "scan_sensitive_json",
    "scan_sensitive_path",
    "scan_sensitive_text",
]
