# Host Semantic Transport Retry v0.1

Status: FROZEN / SUBSEQUENT_BUILD_READY. Production implementation is absent
at this checkpoint. The user approved this invocation-policy successor on
2026-10-22. It is not a correction to a previously retrying implementation.
Main accepted the read-only preflight: READY_WITH_IMPLEMENTATION_BOUNDARIES.

## Scope

Only the normal default Event Grounder, also reused by World, enables this
policy. The generic model client's public `complete()` remains no-retry.
Direct, custom preparers, legacy helpers, producer repair rules, source
requests, prompt versions, semantic verdict/receipt schemas and EI/Core
acceptance remain unchanged. This narrowly supersedes the single-verifier-call
procedure in [semantic validation v0.1](host-grounder-semantic-validation-v0.1.md)
for transport recovery only, not for obtaining a different semantic judgment.

At most one retry is permitted after an exact `ModelTransportError` with code
`NETWORK_ERROR` or `TIMEOUT` and no HTTP status, before any valid completion
has been obtained. No HTTP status (including 401/403/429/5xx), redirect,
credential/configuration/budget failure, malformed/truncated completion,
semantic parse/refusal, evidence rejection, incomplete input, Builder/EI/Core
result, or unknown exception permits retry. No third attempt, source refresh,
prompt repair, model substitution, or alternate provider is permitted here.

## Identity and finite budgets

Freeze the original role/model/configuration, prompts, source registry and
request body. Both attempts must have byte-identical model request bodies,
verified before sending against the same SHA-256. Credentials, headers and
payloads are never retained in the audit. A private per-call timeout override
may be used without mutating the configuration or another client's transport.

At entry to the semantic role let:

- `R = min(2, client.remaining_request_budget)`; existing shared budget usage
  is not reset or refunded. With one remaining request there is no retry.
- `M = config.max_tokens`; cumulative requested output reservation is bounded
  by `R * M`. Each admitted attempt reserves a full `M`; failure gives no
  refund. Do not increase `M` or the client's configured request budget.
- `T = config.timeout_seconds`; the new policy's decision-time budget is
  explicitly `R * T`, measured with a monotonic clock. This is not a claim
  that the old per-call timeout was already a cumulative deadline.

Before every attempt require a remaining request, output reservation and
strictly positive remaining decision time. Its transport timeout is at most
`min(T, remaining_time)`. A response received after the decision deadline is
discarded and cannot enter semantic validation, Builder, EI or Core. The
deadline is a decision/admission limit, not a hard-cancellation guarantee for
an opaque or trickling transport. Do not add a process/thread framework.

The existing input-byte bound applies unchanged on each identical request;
the cumulative bound is at most `R * config.max_input_bytes`. Output-token
reservations are not a cap on actual total billed tokens or dollars. Input
token usage and the first request's billing can be unknown after a lost
response. A second request may duplicate the charge; do not infer idempotency,
refund, zero consumption or zero cost. Model API expenses do not become option
entry fees or Core economic evidence.

## Closed, payload-free audit

Freeze one private audit DTO serialized as:

```text
{
  schema_version: "host-semantic-transport-retry-v0.1",
  request_body_sha256: lowercase SHA-256,
  attempt_limit: R,
  decision_deadline_seconds: R * T,
  output_reservation_limit_tokens: R * M,
  attempts: [
    {
      index: 1 | 2,
      outcome: "response_received" | "transport_failed" | "deadline_exceeded",
      transport_code: admitted ModelTransportError code | null,
      http_status: exact HTTP integer | null,
      timeout_seconds: positive finite number,
      elapsed_seconds: nonnegative finite number,
      reserved_output_tokens: M,
      request_id: nonempty provider request ID | null,
      usage: {prompt_tokens: nonnegative integer | null,
              completion_tokens: nonnegative integer | null,
              total_tokens: nonnegative integer | null} | null
    }
  ]
}
```

The object and every row are closed. Booleans are not integers. Attempts are
ordered, contiguous, one or two once transport starts; an earlier preflight
failure need not invent a transport attempt. A second row requires the first
to be `transport_failed` with `NETWORK_ERROR`/`TIMEOUT`, null HTTP status and
available budgets. Only a successfully parsed transport receipt supplies usage
or request ID; unavailable usage is null, never zero. Nonretryable transport
errors may occupy a final `transport_failed` row but never enable another row.
Late returned receipts may retain known usage/ID, without permitting their
content to be consumed. Rows count transport invocations/reservations, not
proof of server processing or billing. No prompt, response content, source
body, credential, exception text or header is retained.

Persist this audit on normal-route success and failure, including downstream
parse/Builder failure after a returned completion. Preserve it through
producer-error cloning and event-anchor result stamping. Do not relabel the
existing final-call summaries as total HTTP-attempt counts.

New normal stage/submission outcomes use closed v0.4 successors carrying
`semantic_transport`; semantic failures have a closed successor audit carrying
the same object. Old archived versions remain readable and unchanged. The
workbench reads the new versions and displays attempt count and the unknown
billing qualification without implying EI acceptance. Public constructors and
exports remain compatible; implementation-private fields/helpers may be added.

## Required verification

Focused deterministic tests must cover network/timeout then success; repeated
failure stops at two; single remaining request; shared World budget; identical
body/hash and model; conservative output reservation; cumulative deadline and
late response rejection; no retry for HTTP, malformed/truncated output,
semantic/evidence refusal, missing data or arbitrary exceptions; failure and
success audit persistence/reload; constructor bypass/closed-shape rejection;
legacy/custom/Direct compatibility and workbench visibility. Fake clock and
transport tests require no live calls or real credentials.

After BUILD, independent review, focused/full regression, compileall, API
compatibility, documentation and diff checks are required. A live validation
is a separately guarded prospective operation on changed code, never a replay
of either consumed SentinelOne guard or a requirement to obtain acceptance.
