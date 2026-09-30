# Bounded internal Grounder live trial — 2026-09-29

This was one no-retry transport-to-Grounder trial, not an Event Intelligence or
Core product acceptance test. The repository was not modified during the call.

The predeclared source was one retained official IREN SEC Form 8-K URL. A
repository-external script used the existing Tavily Basic Extract client and
external user configuration. Its limits were one request, one reserved credit,
18 seconds, a 100 KB response cap and a 20 KB accepted source-body cap. If
source acquisition succeeded, the script would have made at most one
`deepseek-flash` discovery call and one separate semantic call, each with a
3,000-token output cap and no retry. No raw response, source body, model output
or credentials were printed or persisted.

Observed sanitized outcome:

- Tavily Extract: one request made, one credit reserved; client rejected the
  response with `MALFORMED_RESPONSE`.
- Complete registered source bodies: zero. The exact incompatible field or
  response condition was not retained and therefore is **unknown**.
- Discovery model calls: zero; semantic model calls: zero.
- Host Grounder submission and EI assessment: not reached.
- Provider-reported settled credit usage: unknown; reservation is not a usage
  or billing claim.

This establishes a source-transport compatibility blocker for this one
response, not a negative result about model grounding or SEC evidence quality.
Do not replay this operation as though the failed response were known. The
next bounded diagnostic, if separately undertaken, should capture only the
failing schema path and type without retaining payload text or secrets, then
decide whether a narrow adapter correction is justified. At that time, no
automatic retry, alternate source, schema relaxation or model call was
authorized; later separately authorized operations are recorded below.

## Separate one-request schema diagnostic — 2026-09-30

A separately authorized Tavily Basic Extract diagnostic used exactly one
request and one reserved credit. Sanitized structural inspection confirmed the
rejection at the pre-patch `host_sources.py:1051`:
`results[0].title` was null. Other visible response fields passed structural
checks. No response body, raw payload,
credential or model output was printed or persisted; no DeepSeek call was made.
Provider-reported settled credit usage remains unknown.

The narrow adapter correction accepts an absent, null or exact-string Extract
result title. Non-string non-null titles, source bodies, URLs and all other
response checks remain strict; focused offline tests cover these boundaries.

## Post-fix discovery diagnostics — 2026-09-30

Four separate no-retry Grounder trials used the same official SEC filing URL
and returned the same complete 9,420-byte body, with stable SHA-256 prefix
`89536ce6ff75`. Each trial reserved one Tavily Extract request/credit and
invoked at most one discovery transport; none invoked the semantic role.
Source/body limits, request budgets and the 40 KB model response-byte cap were
unchanged. Discovery outcomes:

| Trial | Discovery max tokens / timeout | Sanitized outcome |
| --- | --- | --- |
| 1 | 3,000 / 18 s | Outer `DISCOVERY_CALL_FAILED`; underlying cause not captured. |
| 2 | 3,000 / 18 s | `TRUNCATED_RESPONSE`, about 12.7 s. |
| 3 | 6,000 / 18 s | `TIMEOUT`, about 18.2 s. |
| 4 | 6,000 / 45 s | `TRUNCATED_RESPONSE`, about 21.6 s. |

Trial 1 retained only the outer runtime code, so its underlying cause is
unknown. Instrumentation captured the underlying `ModelTransportError` codes
for trials 2–4 before runtime wrapping.

Accounting is separate: the initial 2026-09-29 source-compatibility attempt
reserved one request/credit; the follow-up schema diagnostic above was a
separate one-request/one-credit operation; these four post-fix trials reserved
four further requests/credits. Provider-reported settled usage is unknown; no
billing claim is made. No raw body, response, model output or secret was
persisted. No Host Grounder semantic result or EI acceptance was reached.

The post-fix trials established no product success or semantic correctness.
The subsequent offline review corrected discovery/semantic DTO guidance and
exposed Host source metadata to the producer; it did not itself establish a
live result.

## Final DTO-guidance trial — 2026-09-30

After the reviewed discovery/semantic DTO guidance and Host source-metadata
correction, one final no-retry trial used the same official SEC filing and
complete 9,420-byte body (stable SHA-256 prefix `89536ce6ff75`). Tavily Basic
Extract reserved one request/credit. Discovery used a 6,000-token output cap
and 45-second timeout, then returned underlying `TRUNCATED_RESPONSE` after
24.246 seconds. The semantic call count was zero; no EI acceptance was
reached.

The prior pre-next-run reservation total of seven omitted a separate
concision-only discovery trial recorded below. The corrected pre-next-run
count is eight Tavily Extract requests and eight reserved credits: one initial
attempt, one schema diagnostic, four post-fix trials, one concision-only trial,
and this final DTO-guidance trial. This is a reservation-count correction, not
settled provider usage or a bill; settled usage remains unknown.

At that point, the offline DTO prompt omission was corrected, but live runtime
remained blocked at discovery truncation. Stop retries and further cap
increases. The bounded read-only DeepSeek documentation preflight is recorded
below; it supports a cause hypothesis but does not establish the cause.

## Separate concision-only trial — 2026-09-30

Continuation execution evidence records a distinct concision-only trial, not
the final DTO-guidance trial above. It used the same complete 9,420-byte body
and SHA-256 prefix `89536ce6ff75`; discovery used 6,000 tokens and a 45-second
timeout, then returned `TRUNCATED_RESPONSE` after 24.256 seconds. Semantic calls
were zero. It contributes one reserved Tavily Extract request and credit to
the corrected count above; settled usage is unknown.

## Read-only DeepSeek documentation preflight — 2026-09-30

DeepSeek documents thinking as enabled by default at high effort and provides
`thinking: {"type":"disabled"}` to turn it off. The trial set
`thinking_enabled=False` but declared only `("json_mode",)`; `host_model`
serializes the thinking toggle only when the `"thinking"` capability is
declared. The request therefore omitted the disable setting and inherited the
provider default. With a 6,000-token completion cap, reasoning-token use is a
strong truncation hypothesis, not a proved cause: the prior responses did not
retain safe reasoning-token usage metadata. DeepSeek defines `finish_reason`
`length` as reaching the token or context limit. See the official [Thinking
Mode](https://api-docs.deepseek.com/guides/thinking_mode/) and [Chat
Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
documentation.

The trial's `response_format: {"type":"json_object"}` requests JSON output,
not schema-constrained output. DeepSeek documents native `json_schema` format
for the Responses API, not this Chat Completions payload. See [JSON
Output](https://api-docs.deepseek.com/guides/json_mode/) and the [Responses
API](https://api-docs.deepseek.com/api/create-response/). This preflight made
no provider call and establishes neither live success nor semantic
correctness.

## Reviewed thinking-disabled one-shot — 2026-09-30

One reviewed run used the corrected explicit thinking-disabled request with the
same complete 9,420-byte body and SHA-256 prefix `89536ce6ff75`. Tavily Extract
reserved one request/credit. Discovery made one transport call and finished
normally (`stop`) in 13.796 seconds: 4,197 prompt, 4,435 completion, 8,632 total
tokens, and 14,493 content UTF-8 bytes. Reasoning bytes/tokens were null, not
reported as zero. The runtime then raised
`HostGrounderRuntimeError(PRODUCER_ENVELOPE_INVALID)`; semantic calls were
zero and submission was not reached.

This successful discovery completion with thinking explicitly disabled
supports the toggle hypothesis for this trial, but does not establish it as the
sole or universal cause of earlier truncations. Adding this operation to the
corrected pre-next-run count of eight gives nine reserved Tavily Extract
requests and nine reserved credits. This is reservation accounting only, not
settled provider usage or a bill; settled usage remains unknown.

At that point, the next step was an offline DTO diagnostic followed by at most
one separately bounded one-shot to identify the rejection gate. That
diagnostic and its outcome are recorded below. Do not treat normal model
transport completion as Grounder or EI acceptance.

## DTO array-type diagnostic one-shot — 2026-09-30

The separately bounded diagnostic used the same complete 9,420-byte SEC body
and SHA-256 prefix `89536ce6ff75`, one Tavily Extract request/credit, and one
discovery call. Discovery finished normally (`stop`) in 8.707 seconds: 4,201
prompt, 2,845 completion, 7,046 total tokens, and 9,404 content UTF-8 bytes.
Reasoning metadata was null. The safe diagnostic reported
`dto_failed_gate=schema`, module tag `schema`, and line 136 of
`host_grounder_schema.py`, where `bounded_array` rejects a non-array Python
value. The exact array field is unknown; claim/hypothesis/binding counts and
stage/run-match flags remained null because parsing failed. The runtime
raised `PRODUCER_ENVELOPE_INVALID`; semantic calls were zero. No raw response
or model content was persisted.

This adds one reserved Tavily Extract request/credit to a cumulative total of
ten reservations. This is reservation accounting, not settled usage or a bill;
settled usage remains unknown. No further live calls are authorized under this
exhausted diagnostic protocol. That restriction is historical to that protocol;
the separate post-correction validation preregistered below is within the
standing M0–M8 authorization. The prompt-only formatting correction against the
unchanged locked DTO is implemented and independently reviewed: no parser,
schema, Builder, receipt, cap, transport, or verifier-semantic change. Thirty-
seven focused model/schema/runtime tests passed, as did source compilation and
`git diff --check`; no full suite was run. No product success is established.

## New post-format-correction validation preregistration — 2026-09-30

This is one separately bounded validation under the user's standing continuous
M0–M8 authorization, distinct from and not a reopening of the exhausted
diagnostic protocol above. It introduced no provider or methodology change.
The preregistered operation has now been executed once; its outcome follows.

- Use the same official IREN SEC filing URL and the existing reviewed DTO
  diagnostic script unchanged.
- Allow one Tavily Basic Extract request (one credit reserved), then at most
  one `deepseek-flash` discovery call (6,000 output tokens, 45-second timeout).
  If discovery clears all existing strict gates, allow at most one semantic
  call (3,000 output tokens, 18-second timeout). Both model requests explicitly
  disable thinking.
- Preserve the existing request/source limits and byte caps: 100 KB Extract
  response, 20 KB accepted source body, and 40 KB model response. Stop on any
  strict-gate failure; no retry or alternate path.

At preregistration, the cumulative prior Tavily reservation count was ten. The
executed Extract added one reservation, bringing the cumulative count to
eleven. Reservation counts are not settled usage or billing claims.

## Executed post-format-correction validation — 2026-09-30

The one permitted run used the same official IREN SEC filing, complete
9,420-byte body, and SHA-256 prefix `89536ce6ff75`; one Tavily Basic Extract
request reserved one credit. Both model requests explicitly disabled thinking,
as preregistered. Discovery made one call and finished normally
(`stop`) in 7.220 seconds: 5,011 prompt, 2,383 completion, 7,394 total tokens,
and 7,233 content UTF-8 bytes. The DTO passed; stage/run identity flags were
true, with 6 claims, 0 hypotheses, and 7 field bindings. The coverage gate had
no failure. Discovery reasoning metadata was null, not reported as zero.

Semantic verification made one call and finished normally (`stop`) in 8.259
seconds: 5,964 prompt, 2,677 completion, 8,641 total tokens, and 7,337 content
UTF-8 bytes. Its reasoning metadata was also null, not reported as zero. The
runtime returned `SEMANTIC_VERDICT_REJECTED`; submission and EI assessment were
not reached. No retry was made under this completed protocol. The exact
receipt/verdict subgate remains unknown. This outcome does not establish that
the model's semantic judgment was false or that source quality was poor.
Settled provider usage remains unknown.

## Read-only semantic rejection path inspection — 2026-09-30

`run_host_grounder_same_run` calls
`build_semantic_validation_receipt` and converts any exception from it to
`SEMANTIC_VERDICT_REJECTED` at `host_grounder_runtime.py:430–431`. The builder
in `host_grounder_semantic.py` reparses the envelope and verdict, checks
identity/hash, source registry and ordered coverage, validates exact evidence
references, derives claim/hypothesis/coverage outcomes, and finally calls
`validate_semantic_validation_receipt` in `host_grounder_receipt.py`. Therefore
the observed runtime code alone does not identify which subgate failed.

The narrow process-local locator described below implements that approach:
wrap `build_semantic_validation_receipt`, capture only an allowlisted module
tag and deepest source line on failure, then preserve the original result or
exception unchanged. It does not inspect exception text/arguments, frame
locals, or model content, and does not persist payloads. No production edit or
additional provider call was made during this inspection.

## Next semantic-receipt locator preregistration — 2026-09-30

This is a new, standalone bounded one-shot under the standing continuous
M0–M8 authorization. It does not reopen the completed post-format-correction
protocol above, and changes no provider or methodology. Until this new run
executes, the latest outcome remains `SEMANTIC_VERDICT_REJECTED` with the exact
receipt/verdict subgate unknown; this preregistration is not M2 success.

- Use the same official IREN SEC filing URL and existing source/request limits:
  at most one Tavily Basic Extract request (one reserved credit), 100 KB Extract
  response, and 20 KB accepted body.
- Allow at most one `deepseek-flash` discovery call (6,000 output tokens,
  45-second timeout), then only if all current strict gates pass at most one
  semantic call (3,000 output tokens, 18-second timeout). Explicitly disable
  thinking for each call; retain the 40 KB model response-byte cap.
- Stop on any strict-gate failure. No retry or alternate path.

Together, the run allows one Extract and at most two model-role calls. The
implemented external locator is
`/private/tmp/ch_live_grounder_semantic_diagnostic.py`. Its process-local
wrapper reports only an allowlisted semantic/receipt/schema tag and deepest
known source line, returns successful results unchanged, and re-raises the
same error unchanged. On constructor failure only, it also reparses the verdict
with the original parser and identical bounds. If parsing succeeds, it reports
only exact aggregate integer counts for `quote_missing_from_registered_body`,
`quote_unique`, `quote_ambiguous`, `span_matches`, `span_mismatches`, and
`unknown_source`; all six remain null if parsing fails. Body checks use only the
source mapping passed to the builder. No quote, body, source ID, index,
argument, exception text, frame local, or model output is emitted or persisted.
These counts cannot repair or admit a receipt.

Compilation and synthetic offline validation passed, covering unchanged error
and success identity, parse-failure null counts, a unique quote with bad span,
a missing quote, overlapping ambiguous occurrences, an unknown source, and
an oversized end index. Independent pre-execution safety review and targeted
re-review of the counts-only delta passed. No live call or reservation has occurred under this new
protocol; the cumulative Extract reservation count remains eleven until its
execution. Main will commit this preregistration before execution.
No retry is authorized under this protocol.

## Executed semantic-receipt locator protocol — 2026-09-30

The separately preregistered one-shot used the same official IREN SEC filing
and complete 9,420-byte body (SHA-256 prefix `89536ce6ff75`). One Tavily Basic
Extract request reserved one credit. Discovery finished normally (`stop`) in
6.629 seconds: 5,009 prompt, 2,330 completion, 7,339 total tokens, and 7,004
content UTF-8 bytes. The DTO passed with 7 claims, 0 hypotheses, 6 bindings,
and true stage/run identity flags.

Semantic verification made one transport call and stopped with `length` after
9.170 seconds: 5,882 prompt, 3,000 completion (the configured output-token
cap), 8,882 total tokens, and 8,474 content UTF-8 bytes. The underlying error
was `TRUNCATED_RESPONSE`; the outer runtime reported `SEMANTIC_CALL_FAILED`.
The semantic-receipt locator and its evidence-reference counters were not
reached, so all locator fields/counts are null. No receipt was produced and
submission/EI was not reached. No retry occurred. This run's immediate blocker
is semantic output-budget exhaustion at the 3,000-token cap; it does not
resolve the exact receipt/verdict subgate from the earlier completed semantic
response. The outcome does not establish a false model judgment or poor source
quality.

This Extract brings cumulative Tavily reservations to twelve. This is
reservation accounting, not settled usage or a bill.

## Next separate semantic output-budget verification preregistration — 2026-09-30

This is a new, separately bounded one-shot under the standing continuous
M0–M8 authorization. It is not a retry under the completed locator protocol
and is not a request for a prettier response: the prior semantic call reached
its 3,000-token output cap and was truncated. The latest observed blocker
remains semantic output-budget exhaustion; the earlier receipt/verdict
subgate remains unknown because the locator was not reached. This preregistration
is not M2 success.

- Use the same official IREN SEC filing URL and existing source/request bounds:
  at most one Tavily Basic Extract request (one reserved credit), 100 KB Extract
  response, and 20 KB accepted body.
- Allow at most one discovery and, only if all strict gates pass, at most one
  semantic call. Both roles use `max_tokens=6000` and a 45-second timeout;
  explicitly disable thinking. Preserve the existing 80 KB model-input and
  40 KB model-output byte caps and all other budgets, request bounds, and strict
  gates.
- Stop on any strict-gate failure. No retry or alternate path.

The sole intended runtime change is raising the semantic role's token and time
limits to the discovery role's existing 6,000-token/45-second values; discovery
is unchanged. No prompt, parser, DTO/schema, receipt, transport, or verifier
semantics change is authorized. The new external diagnostic is
`/private/tmp/ch_live_grounder_semantic_6000_diagnostic.py`, mechanically based
on the offline-validated locator. Its offline check confirms the semantic-role
configuration and does not make provider calls. At preregistration the
cumulative Tavily reservation count is twelve; the next Extract would bring it
to thirteen if executed. Reservation totals are not settled billing. This
protocol's independent safety review and offline validation passed. It has not
run and awaits Main's preregistration commit before execution; no retry is
authorized.
