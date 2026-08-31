# KUMA Python API reference

[简体中文](api-reference.zh-CN.md) | English

This page documents the stable user-facing Python entry points. Types, defaults,
ranges, side effects, and failure behavior match the current implementation.
KUMA uses keyword-only arguments for its main APIs so call sites remain readable.

## `configure`

```python
from kuma import configure

credential_path = configure(api_key="dfx_your_key_here")
```

<!-- api-parameters:configure:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `api_key` | `str` | Required | Printable ASCII KUMA credential beginning with `dfx_`; maximum 512 encoded bytes, with no whitespace or control characters. |

<!-- api-parameters:configure:end -->

Returns the absolute `Path` of the atomically written user credential file. The
function makes no network request. `KUMA_CONFIG_HOME` redirects the credential
directory. Invalid keys raise `ConfigurationError`; filesystem failures remain
real `OSError` values. The file contains the key and must never be printed or
committed.

## `create_run`

```python
from kuma import create_run

run = create_run(
    repo_path=".",
    requirement_path="requirement.md",
)
```

<!-- api-parameters:create_run:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `repo_path` | `str \| os.PathLike[str]` | `"."` | Repository root visible to the Agent. It is expanded and resolved to an absolute path. |
| `requirement_path` | `str \| os.PathLike[str] \| None` | `None` | UTF-8 requirement file. Official Case generation requires it; a custom Provider can explicitly opt out. |
| `case_provider` | `CaseProvider \| callable \| None` | `None` | Custom Case source. `None` uses the official authenticated Provider. |
| `judge_provider` | `JudgeProvider \| callable \| None` | `None` | Custom Judge. `None` uses the official Provider when `judge=True`. |
| `strategy` | `str` | `"auto"` | `"auto"` delegates selection to the service; another non-empty value is an explicit strategy ID. Unknown strategies are not silently replaced. |
| `max_inputs` | `int \| None` | `None` | Positive Case Input upper bound. Custom Case Providers require a value; official mode uses the public service policy when omitted. |
| `judge` | `bool` | `True` | Run the configured Judge after the final Submission. `False` leaves `run.report` as `None`. |
| `on_failure` | `str` | `"continue"` | `"continue"` advances after `failed`, `timeout`, or `aborted`; `"stop"` closes the Run immediately. |
| `allow_local` | `bool` | `False` | Permit trusted development outside Docker. This does not sandbox the Agent or relax validation/privacy rules. |
| `track_files` | `bool` | `True` | Capture bounded file metadata before and after each Input. |
| `upload_diff` | `bool` | `False` | Include bounded text diffs. Requires `track_files=True` and may expose repository text to the configured Judge. |
| `save_local` | `bool` | `False` | Atomically save Submission JSON under `.kuma/runs/<run_id>/`. It does not replace official submission. |
| `allow_sensitive` | `bool` | `False` | Allow ordinary Evidence flagged by the scanner. It never relaxes the OTel allowlist. |
| `timeout` | `float` | `300.0` seconds | Positive finite timeout for one public HTTP attempt. This is not the total operation wait. |
| `operation_wait_timeout` | `float` | `600.0` seconds | Positive finite total wait for one official asynchronous Case or Judge operation. Timeout preserves recovery metadata. |
| `max_retries` | `int` | `2` | Automatic transient retry count, inclusive range 0–5. Idempotent POST retries reuse one key. |
| `api_key` | `str \| None` | `None` | Per-call `dfx_` key. Resolution order is this value, `KUMA_API_KEY`, then the user credential file. |
| `trace_evidence` | `TraceEvidenceCapture \| None` | `None` | Explicit capture returned by `configure_trace_evidence()`. When omitted, KUMA attempts safe global-provider reuse and otherwise adds a non-blocking warning. |

<!-- api-parameters:create_run:end -->

Returns a synchronous `Run` in `ready` state. Configuration, credential,
isolation, Provider, Case, and public-service failures raise a `KumaError`
subclass with stable `code`, `retryable`, and optional `request_id` fields.
Creating a Run may read the requirement and bounded repository metadata, create
`.kuma/`, acquire the one-active-Run lock, and call the public Backend when an
official Provider is selected.

## `Run`

### `get_input`

<!-- api-parameters:get_input:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `full` | `bool` | `False` | `False` returns only the JSON-compatible payload; `True` returns immutable `KumaInput` metadata and payload. |

<!-- api-parameters:get_input:end -->

Returns the current Input without advancing, or `None` after all Inputs are
committed. Repeated calls before `submit()` return the same Input. Invalid Run
ordering raises `InputProtocolError`.

### `submit`

<!-- api-parameters:submit:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `output` | finite JSON-compatible value | Omitted | Agent result. Explicit output wins; omission is valid for `completed` only when supported OTel instrumentation supplied a final Agent/Workflow output. Explicit `None` is not a completed result. |
| `status` | `str` | `"completed"` | One of `"completed"`, `"failed"`, `"timeout"`, or `"aborted"`. |
| `error` | `str \| None` | `None` | Caller-safe summary for a non-completed Submission. Never include secrets or raw tracebacks. |
| `logs` | `list[str \| Path] \| None` | `None` | Log files whose bounded new bytes are captured. Evidence must be enabled; scope and sensitive-data checks apply. |
| `wait` | `bool` | `True` | Keep `True` when the final Submission triggers Judge. Background Judge polling is not public API. |

<!-- api-parameters:submit:end -->

Returns `TestReport` only when the final Submission completes Judge; otherwise
returns `None`. Submission, Evidence offsets, local records, and Trace byte budget
commit transactionally. Invalid output/state raises `ValidationError` or
`InputProtocolError`; capture and Judge failures remain stable `KumaError` values.

### `judge`

<!-- api-parameters:judge:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `wait` | `bool` | `True` | Must remain `True`; official operation polling is synchronous and bounded internally. |

<!-- api-parameters:judge:end -->

Returns the validated `TestReport`. A failed attempt restores `completed` state,
so retry reuses History and pending operation metadata. Calling before completion
raises `InputProtocolError`; `wait=False` raises `ConfigurationError`.

### `cancel`

`cancel()` has no arguments and returns `None`. It releases Evidence state,
temporary runtime files, and the active-Run lock. Repeated cancellation is safe;
invalid commit/failure states raise `InputProtocolError`.

### Read-only properties

| Property | Type | Meaning |
| --- | --- | --- |
| `run_id` | `str` | Public identifier generated for this Run. |
| `case_id` | `str` | Public Case identifier; never contains a private Rubric. |
| `state` | `RunState` | Current lifecycle state. |
| `history` | `tuple[HistoryItem, ...]` | Immutable committed Input/Submission pairs. |
| `report` | `TestReport \| None` | Final validated Judgment after `report_ready`. |
| `runtime_warnings` | `tuple[str, ...]` | Stable non-fatal Evidence degradation codes. |

## `KumaClient`

Use `KumaClient` for authenticated configuration reads without opening a Run.

<!-- api-parameters:KumaClient:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `api_key` | `str \| None` | `None` | Optional `dfx_` key using the normal environment/file fallback. Read methods require a resolved key. |
| `base_url` | `str` | Public KUMA URL | Public Backend API base. Remote URLs require HTTPS; loopback HTTP is allowed for local integration. Credentials in URLs are rejected. |
| `timeout` | `float` | `30.0` seconds | Positive finite timeout for each GET request. |
| `transport` | public transport callable \| `None` | `None` | Explicit test/integration HTTP boundary. Ordinary users should not provide it. |

<!-- api-parameters:KumaClient:end -->

`entitlements()`, `strategies()`, and `judge_config()` take no arguments and
return validated public mappings. They may raise `KumaAuthenticationError`,
`KumaPermissionError`, or `KumaRateLimitError`; none contacts MCP, a model, or a
database directly.

## OpenTelemetry

Install `kuma-defuzex[otel]` before importing `kuma.otel`.

<!-- api-parameters:configure_trace_evidence:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `tracer_provider` | OTel SDK Provider \| `None` | `None` | Existing Provider exposing `add_span_processor`; `None` selects the current global Provider. KUMA never replaces it. |
| `limits` | `TraceEvidenceLimits \| None` | `None` | Bounded capture configuration. `None` uses the defaults below. |

<!-- api-parameters:configure_trace_evidence:end -->

Returns a `TraceEvidenceCapture` for `create_run(trace_evidence=...)`. Invalid
Providers or limits raise `ConfigurationError`.

<!-- api-parameters:TraceEvidenceLimits:start -->

| Argument | Type | Required/default | Meaning |
| --- | --- | --- | --- |
| `max_spans` | positive `int` | `200` | Maximum ended spans retained per Run. |
| `max_attributes` | positive `int` | `32` | Maximum allowlisted attributes retained per span. |
| `max_events_per_span` | positive `int` | `20` | Maximum allowlisted events retained per span. |
| `max_text_length` | positive `int` | `256` characters | Maximum retained Unicode characters for one allowed text value. |
| `max_total_bytes` | positive `int` | `512000` bytes | Maximum compact JSON bytes across committed Trace envelopes for one Run; must fit the minimum envelope. |

<!-- api-parameters:TraceEvidenceLimits:end -->

## Public result contracts

The main immutable contracts are exported from `kuma`:

| Type | Important fields and meaning |
| --- | --- |
| `KumaInput` | `run_id`, `case_id`, `input_id`, zero-based `index`, `payload_type`, frozen `payload`, public constraints, schema version, and public extensions. |
| `Submission` | Correlated IDs, terminal step `status`, JSON output/error, capture completeness, bounded logs/file Evidence, dropped/missing counters, schema version, and extensions. |
| `HistoryItem` | One `KumaInput` paired with its ID-matching `Submission`. |
| `TestReport` | `report_id`, `run_id`, `status` (`pass`, `issue`, or `insufficient_evidence`), confidence, stop reason, public issues/evidence gaps, and extensions. |
| `CaptureStatus` | Completeness for file snapshot/diff, logs, sensitive scan, and traces. Each component is `complete`, `partial`, `failed`, or `skipped`. |

Private Rubrics, prompts, model settings, and Core records are not part of these
objects. The hash-only upload format is defined separately in the
[Runtime Evidence contract](runtime-evidence.md).

## Error fields

Catch `KumaError` for normal SDK failures. `str(exc)` is a safe user-facing
message. Program logic should use `exc.code`, `exc.retryable`, and
`exc.request_id`; `exc.details` is a bounded public mapping and should be logged
only through an application-approved allowlist.
