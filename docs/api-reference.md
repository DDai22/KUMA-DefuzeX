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

| Argument | Type | Required/default | What it does and when to use it |
| --- | --- | --- | --- |
| `api_key` | `str` | Required | Saves the credential KUMA will use for official Case and Judge requests. Copy the `dfx_...` value issued to you; it must be printable ASCII, contain no whitespace/control characters, and be at most 512 encoded bytes. You do not need this for fully local runs. |

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

| Argument | Type | Required/default | What it does and when to use it |
| --- | --- | --- | --- |
| `repo_path` | `str \| os.PathLike[str]` | `"."` | Chooses the repository being tested. KUMA reads bounded metadata and, when enabled, observes file changes below this directory. Use `"."` when your Python process already runs at the repository root. |
| `requirement_path` | `str \| os.PathLike[str] \| None` | `None` | Points to the UTF-8 file that describes what the Agent should do and which behaviors KUMA should test. Supply it for official Case generation. Omit it only when your custom Case Provider does not need a requirement file. |
| `case_provider` | `CaseProvider \| callable \| None` | `None` | Chooses who creates the test Inputs. Leave `None` to request an official Case from KUMA; pass a callable when your application supplies its own local Case. |
| `judge_provider` | `JudgeProvider \| callable \| None` | `None` | Chooses who evaluates all submitted results and builds the final report. Leave `None` for the official Judge, or pass a callable for your own local evaluation. Ignored when `judge=False`. |
| `strategy` | `str` | `"auto"` | Controls how the official service chooses its Case-generation method. Keep `"auto"` unless the service has given you a specific strategy ID; an invalid ID fails instead of silently choosing something else. |
| `max_steps` | `int \| None` | `None` | Limits how many test steps this Run may contain. For example, `3` allows a Case with one, two, or three steps—it does not force exactly three. `None` lets the official service use its allowed default; custom Case Providers must receive an explicit positive limit. |
| `judge` | `bool` | `True` | Controls whether KUMA evaluates the Run after the last Input. Keep `True` to receive a `TestReport`; use `False` when you only want to execute and record the Case, in which case `run.report` remains `None`. |
| `on_failure` | `str` | `"continue"` | Decides what happens after you submit a step as `failed`, `timeout`, or `aborted`. `"continue"` delivers the next Input; `"stop"` ends the Run immediately. |
| `allow_local` | `bool` | `False` | Allows the Run to start outside Docker for trusted local development. It only bypasses the Docker requirement: it does not sandbox the Agent, expand file access, or weaken validation and privacy checks. |
| `track_files` | `bool` | `True` | Tells KUMA to compare repository file metadata before and after each Input so the Judge can see which files were created, modified, deleted, or renamed. Set `False` when file changes are irrelevant or unavailable. |
| `upload_diff` | `bool` | `False` | Adds bounded changed text to file Evidence instead of sending only paths, hashes, sizes, and change types. Enable only when the Judge needs the actual diff and the repository text is safe to disclose; requires `track_files=True`. |
| `save_local` | `bool` | `False` | Writes a local JSON copy of each committed Submission under `.kuma/runs/<run_id>/`. Use it for debugging or audit records. It does not replace submission to an official Judge. |
| `allow_sensitive` | `bool` | `False` | Lets ordinary Evidence continue when KUMA's scanner flags content as potentially sensitive. Leave `False` unless you reviewed that content and intend to disclose it; this never allows secrets into OTel Trace Evidence. |
| `timeout` | `float` | `300.0` seconds | Limits one HTTP connection attempt to the public KUMA service. Lower it to fail individual network calls sooner. It does not limit the total time spent waiting for Case generation or Judge completion. |
| `operation_wait_timeout` | `float` | `600.0` seconds | Limits the total synchronous wait for one official Case or Judge operation, including polling. If it expires, KUMA raises a retryable timeout and keeps safe recovery metadata so the same operation can be resumed. |
| `max_retries` | `int` | `2` | Sets how many additional attempts KUMA may make after a transient HTTP failure; accepted values are 0–5. Retries reuse the same idempotency key and do not intentionally create another Case or Judge operation. |
| `api_key` | `str \| None` | `None` | Supplies the official-service credential for this Run only. Use it to override the environment or saved credential. With `None`, KUMA checks `KUMA_API_KEY` and then the user credential file. Fully local Provider combinations need no key. |
| `trace_evidence` | `TraceEvidenceCapture \| None` | `None` | Supplies a specific in-process OTel capture and its limits for this Run. Pass the object returned by `configure_trace_evidence()` when you need explicit control. With `None`, KUMA safely reuses a compatible global Provider when available; otherwise the Run continues without Trace Evidence and records a warning. |

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

| Argument | Type | Required/default | What it does and when to use it |
| --- | --- | --- | --- |
| `full` | `bool` | `False` | Chooses how much information your Agent receives. Keep `False` to get only the actual task payload. Use `True` when your integration also needs identifiers, index, payload type, constraints, or extensions from the immutable `KumaInput`. |

<!-- api-parameters:get_input:end -->

Returns the current Input without advancing, or `None` after all Inputs are
committed. Repeated calls before `submit()` return the same Input. Invalid Run
ordering raises `InputProtocolError`.

### `submit`

<!-- api-parameters:submit:start -->

| Argument | Type | Required/default | What it does and when to use it |
| --- | --- | --- | --- |
| `output` | finite JSON-compatible value | Omitted | Sends the Agent's result for the current Input—the value the Judge will evaluate. Pass it explicitly in normal integrations. It may be omitted only when supported OTel instrumentation captured a real final Agent/Workflow output; explicit `None` does not count as success. |
| `status` | `str` | `"completed"` | Records how the current Input ended. Use `"completed"` for a usable result, `"failed"` for an Agent error, `"timeout"` when its deadline expired, or `"aborted"` when execution was intentionally stopped. This value also drives `on_failure`. |
| `error` | `str \| None` | `None` | Provides a short, user-safe explanation when `status` is not `"completed"`. It becomes part of the Submission Evidence, so summarize the failure without secrets, file contents, or raw tracebacks. |
| `logs` | `list[str \| Path] \| None` | `None` | Names local log files whose newly appended bytes should accompany this Submission. KUMA reads only a bounded increment and applies path and sensitive-data checks. Leave `None` when logs are not needed. |
| `wait` | `bool` | `True` | Keeps final Judge execution synchronous: the last `submit()` returns only after the report or an error is available. The current public API requires `True`; background polling is not exposed. |

<!-- api-parameters:submit:end -->

Returns `TestReport` only when the final Submission completes Judge; otherwise
returns `None`. Submission, Evidence offsets, local records, and Trace byte budget
commit transactionally. Invalid output/state raises `ValidationError` or
`InputProtocolError`; capture and Judge failures remain stable `KumaError` values.

### `judge`

<!-- api-parameters:judge:start -->

| Argument | Type | Required/default | What it does and when to use it |
| --- | --- | --- | --- |
| `wait` | `bool` | `True` | Makes `judge()` wait until a final report or error is available. The public Python API is synchronous, so callers must leave this as `True`; use `operation_wait_timeout` on `create_run()` to control the maximum wait. |

<!-- api-parameters:judge:end -->

Returns the validated `TestReport`. A failed attempt restores `completed` state,
so retry reuses History and pending operation metadata. Calling before completion
raises `InputProtocolError`; `wait=False` raises `ConfigurationError`.

### `cancel`

`cancel()` has no arguments and returns `None`. It releases Evidence state,
temporary runtime files, and the active-Run lock. Repeated cancellation is safe;
invalid commit/failure states raise `InputProtocolError`.

### Read-only properties

| Property | Type | What it tells you |
| --- | --- | --- |
| `run_id` | `str` | Identifies this execution in logs, local artifacts, and public service records. |
| `case_id` | `str` | Identifies the public Case being executed. It is safe to correlate but never exposes the private Rubric. |
| `max_steps` | `int` | Reports how many steps the generated Case actually contains. It is at least 1 and never exceeds the explicit `create_run(max_steps=...)` limit, or the service/default limit when that argument was `None`. |
| `state` | `RunState` | Shows which operation is currently legal, such as delivering an Input, submitting, judging, completed, or cancelled. |
| `history` | `tuple[HistoryItem, ...]` | Contains every successfully committed Input and its matching Submission in execution order. It does not include an in-progress step. |
| `report` | `TestReport \| None` | Holds the final Judge result after state becomes `report_ready`; it stays `None` before Judgment or when `judge=False`. |
| `runtime_warnings` | `tuple[str, ...]` | Lists stable warning codes for non-fatal Evidence gaps, such as unavailable automatic Trace capture. The Run can still complete. |

## `KumaClient`

Use `KumaClient` for authenticated configuration reads without opening a Run.

<!-- api-parameters:KumaClient:start -->

| Argument | Type | Required/default | What it does and when to use it |
| --- | --- | --- | --- |
| `api_key` | `str \| None` | `None` | Authenticates configuration reads such as entitlements and available strategies. Pass a key only for this client, or leave `None` to use `KUMA_API_KEY` and then the saved credential. |
| `base_url` | `str` | Public KUMA URL | Chooses the public Backend that receives the client's GET requests. Ordinary users should keep the default. Remote URLs must use HTTPS; loopback HTTP is allowed for local integration, and URLs containing credentials are rejected. |
| `timeout` | `float` | `30.0` seconds | Sets how long each configuration GET may wait for a response before failing. It does not control Case/Judge operation polling. |
| `transport` | public transport callable \| `None` | `None` | Replaces real HTTP with an explicitly supplied transport callable. This is for tests or controlled integrations; ordinary applications should leave it `None`. |

<!-- api-parameters:KumaClient:end -->

`entitlements()`, `strategies()`, and `judge_config()` take no arguments and
return validated public mappings. They may raise `KumaAuthenticationError`,
`KumaPermissionError`, or `KumaRateLimitError`; none contacts MCP, a model, or a
database directly.

## OpenTelemetry

Install `kuma-defuzex[otel]` before importing `kuma.otel`.

<!-- api-parameters:configure_trace_evidence:start -->

| Argument | Type | Required/default | What it does and when to use it |
| --- | --- | --- | --- |
| `tracer_provider` | OTel SDK Provider \| `None` | `None` | Selects the in-process OTel Provider from which KUMA receives ended spans. Pass your application's existing Provider when it is not global; `None` uses the current global Provider. KUMA adds a processor but never replaces or resets the Provider. |
| `limits` | `TraceEvidenceLimits \| None` | `None` | Controls how much Trace data one Run may retain. Pass custom limits for tighter memory/privacy budgets; `None` uses the bounded defaults below. |

<!-- api-parameters:configure_trace_evidence:end -->

Returns a `TraceEvidenceCapture` for `create_run(trace_evidence=...)`. Invalid
Providers or limits raise `ConfigurationError`.

<!-- api-parameters:TraceEvidenceLimits:start -->

| Argument | Type | Required/default | What happens when the limit is reached |
| --- | --- | --- | --- |
| `max_spans` | positive `int` | `200` | After this many ended spans have been retained for a Run, additional spans are dropped and the Evidence reports the drop instead of growing memory without bound. |
| `max_attributes` | positive `int` | `32` | Keeps at most this many safe, allowlisted attributes on each span; additional attributes are dropped and counted. Sensitive attributes remain rejected regardless of this number. |
| `max_events_per_span` | positive `int` | `20` | Keeps at most this many safe OTel events on each span; later events are dropped and reported. |
| `max_text_length` | positive `int` | `256` characters | Truncates each retained allowlisted text value to this many Unicode characters and records that truncation occurred. |
| `max_total_bytes` | positive `int` | `512000` bytes | Caps the compact JSON size of all committed Trace envelopes in one Run. KUMA drops or truncates Trace data to stay within this budget; the value must still fit the smallest valid envelope. |

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
