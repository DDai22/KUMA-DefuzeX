# Detailed Judge assessment and public messages

This SDK supports the optional `kuma.judge_assessment.v1` contract. It requires
a service that explicitly advertises it; installing this SDK does not enable a
server feature. Existing reports and historical experiments are not rewritten.

## Capture all completed public messages

An Agent may deliver an artifact or disclose a failed probe before its final
reply. Passing only that final reply loses this context. Your runner must supply
the actual completed public messages from the current Agent invocation:

```python
from kuma import collect_public_messages

# native_events is the current target invocation's ordered in-memory event list.
messages = collect_public_messages(
    native_events,
    source_actor="target_agent",
    source_complete=True,
)
run.submit(final_output, public_messages=messages)
assessment = run.report.extensions.get("assessment")
print(run.report.extensions.get("claim_coverage_notice", ""))
if assessment is None:
    print("Detailed assessment was not performed")
else:
    print(assessment["task_completion"])
    print(assessment["artifact_quality"])
    print(assessment["behavioral_integrity"])
    print(assessment["claim_coverage"])
```

Run the credential-free example with `python examples/public_messages.py`.
It uses a custom local Case and disables Judge: it demonstrates capture, not a
fabricated official assessment. No model, credentials or network are required.
The example compares default incomplete capture with an explicitly complete toy
stream. In a real integration, use your runner's actual event list, not these demo
messages or a transcript reconstructed from final output or tool logs.

`collect_public_messages(events, *, source_actor="unknown", source_complete=False)`:

| Parameter | Accepted value and purpose |
| --- | --- |
| `events` | Required ordered list/tuple of at most 100000 native event mappings. A completed public message has integer `schemaVersion=1`, `type="item.completed"`, nonnegative integer `sequence`, and `item={id, type:"agent_message", content:str}`. IDs use 1–128 ASCII letters/digits or `._:-`. This function does not read a transcript file, execute event commands or discover an Agent automatically. |
| `source_actor` | One of `target_agent`, `sdk_setup`, `external_evaluator`, `reviewer`, `cross_case_reference`, `unknown`. Default `unknown`. Choose `target_agent` only after isolating that invocation's stream. This is a declaration, not an attestation. |
| `source_complete` | Boolean, default `False`. Set `True` only if this list covers the invocation's entire public stream. It says nothing about execution/network capture or successful behavior. Redaction, unfinished messages and unsupported events prevent complete capture. |

Returns a detached JSON bundle with `public_messages` and `coverage`; input is
unchanged. There is no I/O. Invalid shapes, source ordering or IDs raise
`ValidationError(code="public_messages_invalid")`; limits raise
`LimitExceededError(code="public_messages_too_large")`. Errors do not echo values.
Unknown event/item shapes produce an `unsupported_event` coverage gap rather than
being silently called complete. Known lifecycle events are not messages; reasoning
and tool events are deliberately excluded, not copied into message content.

`Run.submit(public_messages=...)` defaults to `None`, retaining existing behavior.
Omission does not create a message transcript and does not discard separately
captured Agent output or Trace Evidence. Do not set `source_complete=True` merely
because a final reply exists: it declares that all public events for that invocation
were collected, not that the Agent finished the task or its claims are true.
Supply the bundle for each corresponding Input. It is validated and redacted
before Evidence preparation or local Submission persistence. It does not replace
`output`, execute an Agent, or turn public self-report into independent evidence.
Local/custom Judge callers can inspect the immutable
`Submission.extensions["assessment_evidence"]`; their existing return contract
is unchanged. Save-local mode stores the sanitized envelope with that Submission.

## Attribute captured execution explicitly

Message `source_actor` labels messages only, not tools or other runtime facts.
Use `Run.submit(runtime_actors=...)` to declare known actors for specific completed
OTel spans. Install the optional `kuma-defuzex[otel]` dependencies. This ordinary
workflow requires the configured service credentials, an Agent Profile and a
server advertising detailed assessment plus Runtime Trace Evidence:

```python
from opentelemetry.sdk.trace import TracerProvider
from kuma import collect_public_messages, create_run
from kuma.otel import configure_trace_evidence

provider = TracerProvider()
capture = configure_trace_evidence(provider)
tracer = provider.get_tracer("my-agent")
run = create_run(repo_path=".", agent_profile_path="agent-profile.md",
                 trace_evidence=capture, max_steps=1)
step = run.get_input()
actors = []

def execute_probe(actor):
    with tracer.start_as_current_span("execute_tool arithmetic_probe") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", "arithmetic_probe")
        result = sum((1, 2))
        span.set_attribute("gen_ai.tool.call.result", str(result))
        context = span.get_span_context()
        actors.append({"trace_id": f"{context.trace_id:032x}",
                       "span_id": f"{context.span_id:016x}", "actor": actor})
        return result

execute_probe("sdk_setup")
result = execute_probe("target_agent")
# In your runner, use its actual completed public-message events for this step.
events = [{"schemaVersion": 1, "sequence": 1, "type": "item.completed",
           "item": {"id": "reply-1", "type": "agent_message",
                    "content": f"The arithmetic probe returned {result}."}}]
run.submit(str(result), runtime_actors=actors,
           public_messages=collect_public_messages(events,
               source_actor="target_agent", source_complete=True))
provider.shutdown()
```

This demonstrates instrumentation, not an Agent that solves arbitrary generated
Cases: replace the probe with your actual target's tool execution for `step`.
Do not label setup/reviewer work as target activity. Declarations are user
assertions, not attestations or proof that a claim is true.

`runtime_actors` defaults to `None`. Supply a list/tuple of at most 1000 closed
`{trace_id, span_id, actor}` mappings for **this Input only**. IDs are nonzero,
lowercase OTel hex (32/16 characters); use `span.get_span_context()` as above.
Actors are the same six closed values as message actors. Selectors match exactly
one captured span, never names, descendants, an entire trace or an entire mixed
capture. Undeclared spans remain unknown. `public_messages` must also be supplied
(a valid empty-message bundle is allowed). No execution/network completeness is
upgraded; the collector's `unavailable` remains unchanged.

Malformed, missing, duplicate, conflicting or ambiguously captured selectors raise
`ValidationError(code="runtime_actor_invalid")`. Syntax is checked before capture;
resolution occurs after capture and before local Submission persistence. Failure
aborts staged capture without consuming trace budgets, committing log offsets,
appending history or advancing the Input. Correct the declarations and repeat
`submit` for that Input. A dropped/missing span is not guessed or silently ignored.

Local history/save-local retains only the IDs and actor declarations in
`Submission.extensions["runtime_actors"]`. At final Official upload, KUMA resolves
them again against the negotiated, redacted runtime bytes and constructs the
existing provenance ordinals/hashes/span pointers. You never predict hashes or
replace immutable history. Selectors are not new wire fields. Unsupported
Runtime Trace projection or unresolved/conflicting final references fails before
POST; if Submission already committed, the Run remains `completed` and retries
with `run.judge()`, not a second `submit`. After a remote operation exists, recovery
remains GET-only. Manual advanced provenance and selectors cannot overlap with
conflicting actors or duplicate the same reference. No runtime schema changed.

## Attribute an observed final output explicitly

`Run.submit(agent_output_actor=None)` leaves the final output's producer unknown.
If your runner directly received that output from the isolated target invocation,
it may pass `agent_output_actor="target_agent"`. The accepted strings are exactly
`target_agent`, `sdk_setup`, `external_evaluator`, `reviewer`,
`cross_case_reference`, `unknown`; setup/reviewer output must keep that identity.
Do not infer it from a span name, ancestor, error string or the output's contents.

```python
# observed_return is the actual return value of the target invocation for this Input.
# If no public-message events were captured, disclose that instead of inventing them.
run.submit(
    observed_return,
    agent_output_actor="target_agent",
    public_messages=collect_public_messages([]),
)
```

Run `python examples/agent_output_actor.py` for a credential-free example using
an actual deterministic local function as the target; Judge is disabled. In a
real integration, retain real public messages when available. The empty bundle
above is not complete capture and does not synthesize a transcript.

Explicit output attribution requires Runtime Evidence capture, a supplied valid
`public_messages` bundle and `status="completed"`. Null, blank/whitespace-only
strings and empty objects/arrays are not eligible; `0` and `False` are valid
nonempty JSON values. Invalid actors, missing capture/bundle or incompatible
status fail with value-free `ValidationError(code="agent_output_actor_invalid")`
before commit; normal output validation still rejects invalid output types.

The declaration is stored only in local Submission metadata. Official upload
revalidates it and binds existing assessment provenance to the exact final
`/components/<n>/agent_output` leaf, Evidence ordinal and serialized byte hash.
Binding happens **after** privacy redaction and projection, never against the
original sensitive output. Missing/ambiguous final output or duplicate/conflicting
parent/child declarations fail before POST; after commit, retry `run.judge()`.
Old services lacking the needed output/assessment support do not silently discard
the declaration. Existing `runtime_actors` still label only their selected spans.

This names the producer of the whole value, not every speaker in a structured
conversation or quotation inside it. It does not prove execution, make embedded
third-party text an Agent assertion, change any verdict, or upgrade capture to
complete. Core decides whether existing attributable output can support partial
claim review; an SDK actor declaration alone does not guarantee that fallback.

## Record an observed model-call failure without guessing its cause

The existing Runtime Trace contract can retain a model span's OTel status as
`unset`, `ok` or `error`, plus its recorded `gen_ai.operation.name` (for example,
`chat` or `text_completion`). An instrumentation boundary that actually observes
a failed call may set `Status(StatusCode.ERROR)` on that call's span. Do not set
it merely because an Agent's output contains an error-like phrase or is empty.
Status descriptions are not copied into the normalized span; do not add raw
provider diagnostics, credentials, account information or host paths as attributes.

For a span you can attribute to the target invocation, supply its exact
`trace_id`/`span_id` with `actor="target_agent"` through `runtime_actors`, as above.
Setup and reviewer calls must retain their own actor. Unselected spans remain
unknown; the actor is a caller declaration, not authenticated proof. The SDK
binds it to the final uploaded Evidence using the existing assessment provenance
reference: `evidence_index`, `evidence_sha256` and a pointer such as
`/components/2/trace_evidence/spans/0`. Never predict that ordinal or pointer in
application code, and never infer actors from names or message text.

If your runner observed that the step could not finish, it may submit
`status="failed"`, `"timeout"` or `"aborted"` with a short safe `error` summary.
These statuses map to an unverified `agent_response_claim` with `claim="blocked"`
and a hash, not an authenticated infrastructure finding; completed output maps
to `claim="completed"`. Do not relabel a completed step just to influence Judge.
Actor selectors still require a `public_messages` bundle; a genuinely empty
captured stream may use `collect_public_messages([])`, which does not invent a
message or claim full capture.

An observed `error` proves only that instrumentation marked that invocation as
failed. It does **not** establish a vendor outage, insufficient balance, an
environment cause, or whether the Agent submitted an invalid request. It does
not excuse independent false claims or forbidden actions. Task completion,
artifact quality and behavioral integrity remain separate service judgments;
the SDK does not change verdicts or confidence from Trace status, blank output,
or substrings. For example, preserve a genuine statement that a test was not run
alongside the failed-call observation; do not replace other observed behavior
with a generic environment-failure label. Missing capture remains a gap, not
proof the call succeeded or failed. No new failure field or adapter is required
for these existing observations.

## Exact capture fields and limits

Each message has closed fields:

| Field | Meaning |
| --- | --- |
| `message_id` | Unique retained message ID, 1–128 characters. Collector generates `message-<source_event_index>`. |
| `sequence` | Original nonnegative integer event sequence, strictly increasing among retained messages. |
| `source_event_index` | Zero-based index in the supplied event array, strictly increasing; not interchangeable with `sequence`. |
| `source_event_id` | Original item ID, 1–128 characters, or `null` for manually supplied normalized messages. |
| `actor` | The closed actor declaration above. Omission in a manual bundle normalizes to `unknown`, never `target_agent`. |
| `content` | Nonempty completed public text, at most 32768 UTF-8 bytes. Canonical credential redaction runs even on hand-built bundles; there is no `allow_sensitive` bypass. |
| `content_sha256` | Lowercase SHA-256 of retained text's raw UTF-8 bytes, recomputed after redaction. Not a hash of hidden original text. |

At most 200 messages per Judge item across all steps; at most 1 MiB per canonical
assessment Evidence envelope. No text/message truncation. Zero messages is valid:
the SDK never manufactures a final message. Oversize submissions must be handled
by the caller, not silently converted to a complete capture.

`coverage` is closed: `public_messages`, `execution`, `network` each use
`complete|partial|unavailable`, plus unique `reasons` from `source_incomplete`,
`redacted`, `unsupported_event`, `unfinished_message`. The collector always leaves
execution/network `unavailable`; observing messages cannot establish those facts.
Manual contradictory `complete` plus gap reasons is invalid. Redaction applied
by the SDK adds `redacted` and changes public-message completeness to `partial`.
Redaction detects recognized forms, not every possible secret: review input.

An advanced normalized bundle may also include `provenance` (default `[]`, at most
1000 entries). Each entry is exactly `{reference, actor}`. `reference` is
`{evidence_index, evidence_sha256, pointer}`: index 0–49 in the accepted Evidence
list (excluding the Case), exact content UTF-8 SHA-256, and RFC 6901 pointer of
at most 512 characters. The SDK checks the reference against the actual serialized
preceding typed Runtime Evidence parts before POST; it does not resolve host paths.
Each pointer must address an actual `/components/<index>` component or its
descendant, with the same Run/Input/step/Submission coordinates. Legacy `raw_log`
JSON cannot acquire typed execution authority. Conflicting overlapping actor
declarations fail closed. No self
reference, duplicate reference or invented hash is permitted. Core resolves the
accepted content and owns witness semantics. Root pointers in result references
can supply context, but are not valid provenance/action witnesses. Leave
provenance absent when its origin is unknown; never
label setup commands or reviewer tests as target-Agent executions.

## Negotiation, upload and recovery

`OfficialJudgeProvider(..., assessment_contract="auto")` negotiates the detailed
contract when `GET /sdk/judge/config/` advertises
`supported_assessment_contracts=["kuma.judge_assessment.v1"]`. On an older server,
an ordinary Run remains compatible and `report.extensions` has no `assessment`.
Explicit `assessment_contract="kuma.judge_assessment.v1"` requires support;
`None` disables detailed results. Supplied public messages require detailed
support and the `defuzex.assessment_evidence.v1` Evidence advertisement: they are
never discarded into a legacy fallback. Unsupported explicit use raises
`ProviderError(code="assessment_unsupported")` before POST.

Each supplied step gets one separate closed typed part with source
`defuzex.assessment_evidence.v1` and MIME
`application/vnd.defuzex.assessment-evidence+json`. Fields are `schema_version`,
`run_id`, `input_id`, `step_id` (at most 80 characters), `submission_id`,
`public_messages`, `provenance`, `coverage`. Other association IDs are 1–128
characters. IDs must match the Submission. Existing runtime schemas/parts remain
unchanged: messages do not enter `raw_log` or a frozen runtime envelope.

Canonical JSON uses `ensure_ascii=True`, sorted keys, compact separators and no
NaN/Infinity. Manifest hashes bind exact uploaded bytes. Dynamic file/total budgets
still apply, including the Case; a ten-step paired upload needs 21 files, not 20.
The service must advertise capacity accordingly. Batch limits apply per item plus
the existing aggregate byte budget; the SDK never drops steps to fit.

The negotiated result contract participates in request identity and is stored as
non-secret recovery metadata before POST. No message/Evidence body enters the
request ledger. Known operation IDs resume with GET only, including after restart
or advertisement changes. Lost-response retries retain the original contract,
idempotency key and request hash. Missing/malformed negotiated results fail with
`invalid_response` before success/report persistence; retry does not create a new
operation. A previous legacy request is never silently upgraded on recovery.

## Read the result without conflating outcomes

The optional closed assessment contains `schema_version`, three independent axes,
`attributions`, `claims`, `claim_coverage`. At most 262144 canonical UTF-8 bytes.
No private Rubric, raw message transcript or reasoning belongs in it.

| Axis | Status values |
| --- | --- |
| `task_completion` | `completed`, `incomplete`, `unverifiable`, `not_assessed` |
| `artifact_quality` | `satisfactory`, `defective`, `unverifiable`, `not_applicable`, `not_assessed` |
| `behavioral_integrity` | `no_anomaly_observed`, `anomaly_observed`, `unverifiable`, `not_assessed` |

Every axis independently supplies `confidence` (`low|medium|high`), `severity`
(`none|low|medium|high`), up to 16 `evidence_refs`, and 1–8 unique `reason_codes`
from `observed_support`, `observed_violation`, `missing_evidence`, `partial_capture`,
`source_not_attributable`, `not_applicable`, `not_assessed`. Nonnegative/unverifiable
statuses have severity `none`. Task failure is not automatically misconduct;
passing existing tests does not prove an untested compatibility property.

`attributions` has at most 8 closed `{cause, confidence, evidence_refs}` entries.
Cause is `model|input|environment|instruction_conflict|unknown`; multiple causes
are allowed and confidence is independent of severity.

`claims` has at most 100 entries: unique `claim_id` (1–80), safe paraphrase
`summary` (1–1000), `claim_type` (`execution|delivery|artifact_property|reporting|other`),
`source` reference, `verification` (`supported|contradicted|unverifiable`),
`confidence`, up to 16 `evidence_refs`, and `reason_code` from `matched_evidence`,
`contradictory_evidence`, `missing_evidence`, `partial_capture`,
`source_not_attributable`, `not_independently_verified`. Support/contradiction need
independent non-root witnesses, not the claim itself. The narrowly defined
exception is a `reporting` contradiction between conflicting statements inside
the same public message; it does not prove tool execution. Missing evidence is
unverifiable, not contradiction; an Agent's disclosed failed probe is not hidden
merely because a later short reply omits it.

`claim_coverage` contains `status` (`complete|partial|unavailable`), unique
`reason_codes` (the four capture reasons plus `claim_limit|not_assessed`), and up
to 200 `reviewed_message_refs`. A complete declaration accounts for every supplied
target message, including those without extracted claims. It is not proof the
model found every natural-language claim, nor proof an Agent never uploaded data.
SDK validates closed syntax/bounds/privacy; Core resolves witnesses and performs
the assessment. The legacy top-level report status remains available but must not
be treated as three detailed passes.

## Local readable explanations

After validating an Official Judgment, the SDK adds optional display fields to
`Report.extensions`:

- `claim_coverage_notice`: a static English string under 600 characters whenever
  a negotiated assessment exists, **including pass reports**. It separately
  displays the Judge's `complete`, `partial` or `unavailable` claim-review coverage.
  `partial` and `unavailable` are not verdicts, and `complete` is not proof every
  claim is true or every original event was captured. Read the unchanged
  `assessment.claim_coverage.reason_codes` and `reviewed_message_refs` for detail.
  Legacy omission produces no notice, not a fabricated `unavailable` assessment.

- `explanation`: a static English summary (under 1600 characters) of the overall
  non-pass verdict and any validated global attribution or axis `missing_evidence` /
  `partial_capture` reason. These are explicitly **Judge-reported claims**, not
  independent proof that capture failed or that the Agent is defective.
- `step_explanations`: one `{step_id, message}` entry per non-passed step, in
  server order. Each message is static English under 200 characters; `step_id`
  is the validated public step identifier. Issue steps point to their existing
  issue-ID references. Inconclusive steps state that no reliably associated
  cause is available. Global environment/model/input causes are never assigned
  to individual steps: the current assessment does not provide that binding.

```python
if report is not None:
    print(report.extensions.get("claim_coverage_notice", ""))
    print(report.extensions.get("explanation", ""))
    for entry in report.extensions.get("step_explanations", ()):
        print(entry["step_id"], entry["message"])
```

Passed reports omit `explanation` and `step_explanations`, but retain the separate
claim-coverage notice when assessment was negotiated. Reports without non-passed
steps omit the step list. Older saved reports and custom Judge reports need not have any
field. Newly saved Official reports preserve these local explanations; existing
reports are not rewritten. Remote fields with these names cannot supply their
text. No model call, private Evidence read or new server field is involved.
Original status, `step_results`, issue-ID references, issues, `evidence_gaps`
and assessment remain unchanged. Consult those source fields for actual findings
and factual gaps; a local explanation is not an additional finding.
