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

At preregistration, this was a new, separately bounded one-shot under the
standing continuous M0–M8 authorization. It was not a retry under the completed
locator protocol or a request for a prettier response: the prior semantic call
reached its 3,000-token output cap and was truncated. At that time, the earlier
receipt/verdict subgate remained unknown because the locator was not reached.
This preregistration was not M2 success; its execution is recorded below.

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
Independent safety review and offline validation passed before execution. Main
committed the preregistration before the one-shot recorded below; no retry is
authorized under that protocol.

## Executed semantic 6,000-token verification — 2026-09-30

The preregistered one-shot used the same official IREN SEC filing and complete
9,420-byte body (SHA-256 prefix `89536ce6ff75`). One Tavily Extract request and
credit were reserved, bringing cumulative reservations to thirteen; this is
not settled billing. Discovery made one call (`finish_reason=stop`) in 4.760
seconds: 5,012 prompt, 1,492 completion, 6,504 total tokens, and 4,590 content
UTF-8 bytes. Reasoning-token metadata was null. The DTO passed with 4 claims,
0 hypotheses, and 3 bindings; stage/run identity flags were true.

Semantic verification made one call (`finish_reason=stop`) in 6.766 seconds:
5,098 prompt, 2,217 completion, 7,315 total tokens, and 6,265 content UTF-8
bytes. Reasoning-token metadata was null. Receipt construction failed as
`SEMANTIC_VERDICT_REJECTED`; the safe locator reported gate `semantic`, module
`semantic`, line 310. At `host_grounder_semantic.py:309–310`, the exact-body
slice check failed after the source/hash guard for the failing reference; the
diagnostic did not separately count hash mismatches. Counts: 11 refs with
unique quote occurrences, 0 ambiguous, 0 missing, 0 span matches, 11 span
mismatches, and 0 unknown sources. No receipt or submission/EI was produced;
no retry occurred.

The related check at `host_grounder_semantic.py:324–328` also requires verifier
references for supported field bindings to match the envelope binding's
source, quote, start, and end. That comparison follows the failing span check
and was not reached; this run did not establish whether the producer binding
offsets themselves were correct. The prior exact receipt subgate from the
earlier normally completed semantic response remains unknown.

## Tier-A contract freeze: Host-derived spans

Independent review core-PASSed this contract after two text clarifications.
Status is **FROZEN — SUBSEQUENT_BUILD_READY**. The bounded implementation was
independently reviewed and passed 81 focused Host-Grounder tests, 18
Host-Model tests, compilation, diff-check, and the 1,602-test full suite. No
live call or M2/product success is claimed. The frozen path uses exact wire `schema_version` values
`grounder-output-v0.2` and `semantic-verdict-v0.2`, maps Host-derived spans to
strictly revalidated internal `grounder-output-v0.1` and
`semantic-verdict-v0.1` shapes, and records provenance in a closed same-run
sidecar. Receipt/Builder v0.2 stay unchanged; legacy APIs remain fail-closed.
The exact sidecar keys/version literals, canonical UTF-8 digest rules,
same-run external digest record, unchanged gates, and adversarial cases are
frozen in the [contract](host-grounder-quote-localization-v0.1.md). This is
build authorization only, not M2 or product success.

## Quote-localization validation preregistration — 2026-09-30

At preregistration this was a separate one-shot using the frozen quote-only
Host-localization route. The latest prior outcome was the semantic 6,000-token
run's `SEMANTIC_VERDICT_REJECTED`, with thirteen cumulative Tavily reservations.
The script is `/private/tmp/ch_live_grounder_quote_localization_v0_1.py`; its
synthetic offline validation and compilation passed. Mill's script safety
review passed. Implementation and preregistration were committed and pushed
as `b759e24` before the one-shot.

- Reuse only the same official SEC URL and require the same complete 9,420-byte
  body with SHA-256 prefix `89536ce6ff75`; otherwise stop before model calls.
- Allow at most one Tavily Basic Extract request/credit (18-second timeout,
  100 KB response cap, 110 KB byte budget, 20 KB accepted body cap).
- Allow at most one `deepseek-flash` discovery and, only after every existing
  strict gate passes, at most one semantic call. Both use 6,000 output tokens,
  45 seconds, JSON-object mode, explicit thinking-disabled capability, one
  request budget, 80 KB input and 40 KB output byte caps.
- Preserve all DTO, identity, coverage, evidence, receipt, Builder, source, and
  EI gates. Stop on any failure; no retry, alternate source, or fallback.

The explicit versioned route uses quote-only producer/verifier DTOs, Host
unique-exact quote localization, and the caller-owned run/input-bound
write-once audit holder. The script reports only bounded usage/shape counters,
normalization status, and the sidecar digest; it never prints or persists raw
content, normalized payloads, sidecar JSON, or credentials. Offline validation
confirmed the synthetic route finalizes the holder, yields strict internal
v0.1 normalization, preserves stage/run checks, and emits only the safe digest
and aggregate fields. Independent review passed for the holder change; this
pre-registration is not a live result or M2 success.

The preregistration projected one Extract reservation, bringing the cumulative
count from thirteen to fourteen; the observed reservation is recorded below.
Reservation accounting is not a settled usage or billing claim.

## Executed quote-localization validation — 2026-09-30

The committed one-shot script ran exactly once. It reserved one Tavily Extract
request and credit and invoked the transport once, but failed with
`TavilyTransportError` / `NETWORK_ERROR`; HTTP status was null. The source was
not complete, with zero body bytes and no SHA-256 prefix. Discovery and
semantic invocation, reservation, and transport counts were all zero. Their
response metadata, DTO diagnostics, and quote-localization audit fields remain
null; no holder was finalized, and no receipt, submission, or EI result was
produced.

No retry or escalated rerun was made: the sole Extract slot was already
reserved and the no-retry protocol was exhausted. The transport error does not
establish whether the provider received the request; settled usage and billing
remain unknown. Cumulative Tavily reservations are fourteen, not a settled
usage total. This run did not reach or test quote localization, model behavior,
semantic validation, or EI acceptance.

## Read-only local proxy connectivity diagnosis — 2026-09-30

The failed run command was
`PYTHONPYCACHEPREFIX=/private/tmp/ch-mvp-pycache python3 /private/tmp/ch_live_grounder_quote_localization_v0_1.py`
with `sandbox_permissions=use_default` (the tool default). The script process
completed with exit code 0 and no session ID; its sanitized result recorded
`proxy_configured=false`, one Tavily transport invocation, and one request and
credit reservation before `NETWORK_ERROR`. It recorded no HTTP status, body,
or model calls.

A separate TCP connect-and-close check to `127.0.0.1:7890` returned errno 1
under `use_default`; the same check with `sandbox_permissions=require_escalated`
connected successfully. Neither check sent HTTP data or contacted a provider.
This shows the default sandbox could not reach that local socket and escalation
could; because the run had no configured proxy, this is a possible cause of
the Tavily failure, not proof of its cause or of whether Tavily received the
request.

## New network-context-corrected protocol preregistration — 2026-09-30

This is a new, separately preregistered operation, not a retry or reopening of
the closed one-shot above. The reviewed script code remains unchanged at
`/private/tmp/ch_live_grounder_quote_localization_v0_1.py`. Any execution must
start with `sandbox_permissions=require_escalated`; do not first try the default
sandbox.

- Use the same SEC URL and pinned complete body (9,420 bytes, SHA-256 prefix
  `89536ce6ff75`); otherwise stop before model calls.
- Allow one Tavily Basic Extract request/credit (one URL, 8 KB request, 100 KB
  response, 18-second timeout/time budget, 110 KB byte budget, 20 KB accepted
  body cap), then at most one discovery and one semantic call.
- Both model roles remain at 6,000 output tokens and 45 seconds, with one
  request each, JSON-object mode, thinking disabled, 80 KB input/40 KB output
  caps, and all existing strict gates.
- No retries, alternate source, fallback, prompt change, or output-cap increase.

This changes only the execution network context after the connect-only evidence;
it is not a prettier-reply experiment. At preregistration cumulative Tavily
reservations are fourteen; execution would make the count fifteen if the Extract
reservation occurs, not a settled usage or billing claim. The preregistration
is not execution or M2 success. Main committed and pushed it before the single
run recorded below.

## Executed network-context-corrected quote-localization protocol — 2026-09-30

The unchanged `/private/tmp/ch_live_grounder_quote_localization_v0_1.py` was
executed exactly once with `sandbox_permissions=require_escalated` from the
start, using:

```sh
PYTHONPYCACHEPREFIX=/private/tmp/ch-mvp-pycache python3 /private/tmp/ch_live_grounder_quote_localization_v0_1.py
```

The process exited 0 and emitted only sanitized aggregate diagnostics. Tavily
transport was invoked once; one Extract request and credit were reserved. It
returned the complete pinned 9,420-byte SEC body (SHA-256 prefix
`89536ce6ff75`), and `proxy_configured=true`. Discovery was invoked once and
stopped normally after 6.604 seconds: 5,017 prompt, 2,174 completion, and 7,191
total tokens; content was 6,427 UTF-8 bytes. `finish_reason=stop`; reasoning
token and reasoning-content-byte metadata were null.

The quote-only producer DTO then failed with
`PRODUCER_ENVELOPE_INVALID` at the `schema` gate in `quote_localization`,
production line 103. Here `schema` is the safe diagnostic's parse-stage gate
label, not proof of malformed JSON or a generic schema defect. The static
implementation at `host_grounder_quote_localization.py:103` raises
`ValueError("quote is ambiguous")` on the second exact occurrence; advancing
the search start by one code point counts overlapping matches. This proves
that at least one producer binding quote had multiple exact occurrences in its
identified body. The exact binding field/index, number of ambiguous bindings,
and total occurrence count remain unknown; no quote text was exposed. Claim,
hypothesis, and binding counts, stage/run flags, and quote occurrence/span
counters were null because parsing failed. Producer bytes were retained with
status `producer_retained_not_normalized`; audit finalization was false and the
sidecar digest was null. Semantic call/reservation/transport counts were zero.
No receipt, submission, or EI outcome was produced. No semantic judgment or
EI result was reached. No retry or alternate call occurred.

The Extract reservation raises cumulative Tavily reservations from fourteen
to fifteen. This is reservation accounting, not settled usage or billing.
The run resolves the prior network-context uncertainty only for this
execution: source retrieval and discovery completed under the escalated
context. It does not prove the previous `NETWORK_ERROR` cause, and it did not
complete quote localization, semantic validation, or a live Grounder run.

## Post-run versioned prompt clarification — 2026-09-30

Static review localized the producer failure to an ambiguous binding quote;
the exact binding field/index and total match counts remain unknown. The new
`DISCOVERY_SYSTEM_PROMPT_V0_3` now explicitly asks for a unique, unchanged
verbatim binding quote with enough context and no model-selected position. The
new `SEMANTIC_SYSTEM_PROMPT_V0_4` applies the same uniqueness/context rule to
every verifier evidence reference. Both count overlapping matches, prohibit
paraphrase/splicing and ambiguous numeric-only quotes. Unresolvable items
remain governed by existing rules. A unique quote may support a selected
`contradicted` assessment; the prompt does not downgrade it solely because of
that label. Legacy prompts, wire DTOs, schema/receipt/verifier behavior, and
acceptance semantics are unchanged; no wire DTO or verifier outcome change was
made. New explicit-route
audit sidecars use schema `host-grounder-quote-localization-audit-v0.2` with the
same closed key set; prior v0.1 records remain unchanged. Focused validation
passed 24 runtime, 8 schema, and 18 model tests plus compilation. Mill's final
independent review passed; documentation link/fence checks and diff-check
passed. No live retry was made.

## Draft follow-up validation preregistration — 2026-09-30

This is a separate bounded validation of the clarified prompt text, not a
retry of the completed network-context-corrected protocol. Mill's independent
review passed. It is not committed or executed; Main will decide after commit
and quota check. No live call is authorized by this draft.

- Use the unchanged reviewed script
  `/private/tmp/ch_live_grounder_quote_localization_v0_1.py` and require
  `sandbox_permissions=require_escalated` from startup; never try the default
  sandbox first. The script uses the updated v0.3 discovery and v0.4 verifier
  prompt constants.
- Require the same official SEC URL and complete 9,420-byte body with SHA-256
  prefix `89536ce6ff75`; otherwise stop before any model call.
- Keep the same bounds: at most one Tavily Basic Extract request/credit (one
  URL, 8 KB request, 100 KB response, 18-second timeout/time budget, 110 KB
  byte budget, 20 KB accepted-body cap), then at most one `deepseek-flash`
  discovery call and, only if strict gates pass, at most one semantic call.
  Each role keeps 6,000 output tokens, a 45-second timeout, JSON-object mode,
  thinking disabled, and 80 KB input/40 KB output byte caps.
- Preserve every existing strict gate and all other source/request bounds.
  No retry, alternate source, fallback, schema/DTO/parser/runtime change, or
  output-cap change.

The sole intended input difference is the versioned prompt clarification; the
script and execution budgets stay unchanged. Current cumulative Tavily
reservations are fifteen. If the Extract reservation occurs, the next run
would bring that count to sixteen; this is not settled usage or billing.

## Executed quote-localization follow-up — 2026-10-01

The unchanged reviewed script `/private/tmp/ch_live_grounder_quote_localization_v0_1.py`
was run exactly once with `sandbox_permissions=require_escalated` from startup.
The complete pinned SEC body was returned: 9,420 bytes, SHA-256 prefix
`89536ce6ff75`. Discovery completed once and stopped normally in 5.619 seconds
with 5,093 prompt, 1,860 completion, and 6,953 total tokens; content was 6,040
UTF-8 bytes and `finish_reason=stop`. Reasoning-token and reasoning-content
metadata were null.

The producer DTO failed closed as `PRODUCER_ENVELOPE_INVALID`, diagnostic gate
`schema`, module `quote_localization`, production line 106. Static code at
`host_grounder_quote_localization.py:106` raises `ValueError("quote is missing")`
after finding no exact occurrence. In this parser that lookup is for a
producer `field_bindings[].quote`; at least one such quote had no exact match
in the body selected by its registered source ID. The exact binding field or
index and number of missing quotes are unknown. No quote text was exposed or
persisted. Producer bytes were retained but not normalized, and the audit
sidecar was not finalized.

Semantic had zero reservations, invocations, or completed calls. No receipt,
submission, or EI outcome followed; no retry occurred. The Extract reserved one
request and credit, raising cumulative Tavily reservations from 15 to 16. This
is reservation accounting, not settled usage or billing. This result does not
establish semantic failure or a completed live Grounder/M2 outcome.

## Evidence-catalog route one-shot preregistration — 2026-10-01

**EXECUTED ONCE / SOURCE_BODY_MISMATCH.** The following protocol was registered
before execution. This is a new bounded mechanism-validation
protocol for `run_host_grounder_same_run_evidence_catalog_v0_1`, not a retry of
the completed quote-localization attempts above. The reviewed external runner
is `/private/tmp/ch_live_grounder_evidence_catalog_v0_1.py`, SHA-256
`4e408943f14d56653fc24879dde3b28ee0909829d65147f8b1942cb887f1834e`.
Its synthetic offline route check passed with fake model transport, including
the explicit JSON-object request, `thinking=disabled`, 6,000-token/45-second
role configuration, one request per role, and audit finalization. This is
offline-only evidence, not a live provider result or M2 success. The runner's
default mode is offline; this preregistration does not execute its live mode.
Main must explicitly authorize this registered one-shot execution under the
user's continuing bounded-work authorization; it must start with
`sandbox_permissions=require_escalated`; invoke only the explicit `--live`
mode, not the default offline mode.

Prepared invocation (not run):

```sh
PYTHONPYCACHEPREFIX=/private/tmp/ch-mvp-pycache python3 /private/tmp/ch_live_grounder_evidence_catalog_v0_1.py --live
```

- Pin `https://www.sec.gov/Archives/edgar/data/1878848/000114036126023427/ef20075181_8k.htm`
  and the complete extracted body at 9,420 UTF-8 bytes with SHA-256 prefix
  `89536ce6ff75`; stop before model calls on any mismatch.
- Allow one Tavily Basic Extract request and credit for one URL, with the
  existing 8 KB request, 100 KB response, 18-second timeout/time budget,
  110 KB byte budget, and 20 KB accepted-body cap. Then allow at most one
  discovery call and at most one semantic call.
- Keep both `deepseek-flash` roles at request budget 1, 6,000 output tokens,
  45 seconds, JSON-object mode, explicit thinking disabled, 80 KB input and
  40 KB output caps. Preserve `max_json_bytes=40,000`, 8,000-byte string and
  32-item array limits, the 20 KB source-body cap, and every existing strict
  identity, coverage, receipt, verifier, and Builder gate.
- Pass explicit catalog limits: `max_catalog_entries=32`,
  `max_catalog_paragraphs=128`, and `max_catalog_bytes=24,000`. The entry
  ceiling shares the existing 32-item array bound; paragraph counting is
  separate. Any exceeded catalog bound fails closed without partial output
  or truncation. The full source/catalog/prompts must still fit the existing
  80 KB model-input bound.
- Use discovery prompt `host-grounder-discovery-prompt-v0.4` with producer
  wire `grounder-output-v0.3`; use verifier prompt/validator
  `host-grounder-semantic-verifier-prompt-v0.5` with verifier wire
  `semantic-verdict-v0.3`. Internal normalized producer/verifier shapes remain
  v0.1; semantic receipt schema `semantic-validation-v0.2` and existing
  receipt/Builder behavior are unchanged. The retained audit uses schema
  `host-grounder-quote-localization-audit-v0.3`; catalog schema and generator
  are `host-grounder-evidence-catalog-v0.1` and
  `host-evidence-paragraph-generator-v0.1`.

The Host catalog assigns deterministic IDs to exact registered paragraph
spans; that lexical localization does not establish factual meaning or
semantic support. The semantic verifier still assesses evidence against the
registered full source body. A facts-only result with zero hypotheses is not
itself a failure; no hypothesis or EI outcome is to be forced. No retry,
alternate source, fallback, or semantic interpretation by catalog ID is
authorized by this preregistration.

Current cumulative Tavily reservations are sixteen. If this protocol reaches
and reserves its Extract request, the cumulative reservation count becomes
seventeen; this is reservation accounting, not settled usage or billing.

### Registered execution result — 2026-10-01

The reviewed script hash was unchanged and its explicit live mode ran once
with escalation from the start. The single Extract returned 9,423 UTF-8 bytes,
SHA-256 prefix `00ecc509846b`, rather than the registered 9,420-byte body and
`89536ce6ff75` prefix. The source pin gate stopped the protocol with
`SOURCE_BODY_MISMATCH` before discovery or semantic invocation. Neither role
was called; there was no retry or replacement source, normalized envelope,
semantic receipt, Builder submission, or EI result.

One Tavily transport invocation reserved one request/credit, bringing cumulative
reservations to seventeen, not settled usage or billing. The mismatch establishes
only that this extracted body differs from the registered source snapshot; it
does not identify the cause, prove an incomplete source, or establish semantic
failure. No raw source/model payload was persisted. A future source-version
protocol must be separately declared; silently replacing the old pin and
rerunning this completed protocol is not authorized.

### Source-body drift follow-up — 2026-10-01

The preceding run's one-URL Tavily result passed the client checks for
`coverage=COMPLETE`, one returned body, zero failed extracts, exact URL, and a
nonempty body. The runner then failed only its historical byte/hash pin with
`SOURCE_BODY_MISMATCH`. Here, `COMPLETE` means the requested extraction had no
failed URL entry; it is not proof that the extracted text is the complete
official filing. The runner's `source_complete=false` was its post-pin
acceptance flag, not evidence of incomplete Tavily coverage.

The observed body was 9,423 UTF-8 bytes with SHA-256 prefix
`00ecc509846b`. The 3-byte difference from the old 9,420-byte pin does not
identify its cause. The run stopped before constructing a Host source object,
per-run source snapshot, or audit record. Its body was not retained after
process exit, so it cannot be reused; only the reported length and hash prefix
remain. The prior pin and its result remain unchanged. The completed run brings
cumulative Tavily request/credit reservations to seventeen; this is reservation
accounting, not settled usage or billing.

### Source-snapshot acquisition protocol v0.1 — 2026-10-01

**EXECUTED ONCE / SNAPSHOT RETAINED.** The following source-only acquisition
was registered before execution. It is not a retry
and not a replacement of the historical pin. Main reviewed the bounded runner;
this protocol must be committed before any live call. The external runner is
`/private/tmp/ch_live_grounder_source_snapshot_v0_1.py`, SHA-256
`d41bda5c689dccc6bdcdd38fccd4bb0e42cf0378a21bdd9e40fb45bb10c4f331`.
Compilation and its synthetic offline writer check passed; the offline check
made zero network calls and is not an Extract result.

If later authorized, run only the explicit source-only mode:

```sh
PYTHONPYCACHEPREFIX=/private/tmp/ch-mvp-pycache python3 /private/tmp/ch_live_grounder_source_snapshot_v0_1.py --extract
```

- Make at most one Tavily Basic Extract request/credit for the same SEC URL
  above. Retain the existing request/response, 18-second timeout and time,
  110 KB aggregate-byte, one-URL, and 20 KB body bounds. No retry or fallback.
- Persist only the exact returned registered body as UTF-8 bytes plus a
  separate metadata file in a unique directory directly under `/private/tmp`.
  The directory is mode `0700`; files are mode `0600`. Metadata records the
  exact source URL and ID, retrieval time, byte length, full SHA-256, and
  `PENDING_BODY_REVIEW`. Do not save the provider/HTTP response envelope,
  credentials, or body in the repository, Git, or logs; command output contains
  aggregate metadata only.
- Review source quality from the retained body itself before adopting it.
  Tavily `coverage=COMPLETE` records successful extraction coverage for the
  requested URL only; it is not evidence that the body is a complete or
  authoritative rendering of the official filing. The snapshot is a stable
  input artifact, not factual authority. Neither it nor the prior 3-byte
  mismatch establishes why the bodies differ.
- A later model-only run requires its own preregistration and authorization. It
  must verify the retained file against its full hash and byte count, then
  supply that same exact body to both model roles in one Host per-run snapshot.
  It must not Extract again. The exited 9,423-byte body is unavailable and is
  not this snapshot.

The source-only runner has a one-request/one-credit ceiling. Cumulative
reservations currently stand at seventeen; if this new Extract reserves its
request/credit, the count would become eighteen. These are reservations, not a
settled bill. No source-only Extract or model call is authorized or executed by
this registration alone; Main will explicitly authorize the single execution.

#### Acquisition and local catalog readiness result — 2026-10-01

Main authorized the registered source-only execution after script review and
commit. Its hash matched registration; the escalated one-shot Extract returned
one entry and no failures. The 9,423-byte UTF-8 body was retained outside the
repository with full SHA-256
`00ecc509846b657702081827db78a220b8ff51a9bacd19537339575e17ee6e29`.
The unique private directory is mode 0700 and its body/metadata files mode
0600. Local checks verified hash, length, encoding, and metadata agreement.
Only finite structural markers were checked; they do not prove official filing
completeness, issuer identity, or factual authority. The source review remains
limited to those checks; no model or EI result was produced.

Local catalog preflight found 60 paragraphs, 12 excluded as nonunique, none
overlong, and 48 eligible entries. The registered 32-entry/32-array limits
therefore fail before model invocation. Main separately declared a local
64-entry/64-array capacity preflight, retaining 128 candidate paragraphs,
8,000-byte strings, and the 24,000-byte catalog ceiling. This includes every
eligible entry rather than selecting Top-N, but the complete catalog still
exceeds the unchanged byte ceiling. No valid catalog or model-input byte count
was returned, and neither model request was constructed. No further capacity
increase, truncation, new script, retry, or model-only live protocol followed.

This establishes a declared operational-capacity blocker for this retained
source, not a provider-semantic or EI rejection. A future complete-catalog
capacity protocol requires explicit preregistration and request-budget checks;
this record does not authorize further tuning or invocation. Cumulative Tavily
reservations are eighteen (not settled usage/billing). No new model calls,
credentials, raw HTTP/provider envelopes, or source bodies entered Git/logs.

### Bounded model-only catalog preregistration v0.1 — 2026-10-01

**NOT EXECUTED; NOT LIVE AUTHORIZATION.** This distinct preregistration follows
the catalog-capacity preflight. It does not amend or replace any completed
trial. Main must explicitly authorize the registered one-shot execution under
the user's continuing bounded-work authorization before invoking the runner's
`--model-only` mode. No source acquisition, model call, retry, commit,
or production-code change occurred while preparing this protocol.

Prepared runner: `/private/tmp/ch_live_grounder_catalog_model_only_v0_1.py`,
SHA-256
`71c991911b5333cc1f596d2aa08bb98d21bd923f7de573d6b43139ed37e87e4e`,
33,148 bytes. Its default mode is offline with fake clients. It reuses the
existing Grounder runtime and reviewed bounded configuration/error/report
helpers. It has no source-acquisition integration. The model-only branch uses
the existing `ModelCredential` external resolver; it never reads credential
files itself. Aggregate-only reporting excludes source/model payloads and
exception messages, arguments, and locals. Audit payloads remain in memory and
are not persisted.

The registered immutable input is
`/private/tmp/ch_grounder_source_snapshot_a8lfydaw/registered-body.utf8`,
9,423 bytes, SHA-256
`00ecc509846b657702081827db78a220b8ff51a9bacd19537339575e17ee6e29`.
Preparation rechecked its strict UTF-8 decoding, full hash and length, the
0700 directory and 0600 files, and the metadata's original retrieval time
`2026-10-01T07:54:21.398098+00:00`. The Host source record carries that
retrieval timestamp, not the run time. Metadata remains
`PENDING_BODY_REVIEW`; retrieval coverage and this stable snapshot do not
establish source completeness, issuer identity, authority, or freshness. The
same unchanged body is bound in one new run and supplied to both model roles;
there is no refetch. Registered run ID:
`catalog-model-only-20261001-71e458b3c38846c7a5f72ed1774d153c`.

#### Exact local sizing and fixed bounds

The first sizing pass used the repository catalog builder with an explicit
262,144-byte catalog ceiling solely for local measurement. It made two fake
transport invocations through the existing model client with credential
resolution mocked and zero external requests. Results:

- 60 candidate paragraphs; 12 nonunique exclusions; zero overlong; 48 eligible
  entries.
- Complete canonical catalog: **24,070 bytes**. The old 24,000-byte cap is 70
  bytes too small. The preregistered runtime cap is **32,768 bytes**; the
  measurement-only 262,144-byte ceiling is not a runtime authorization.
- Complete serialized discovery request body: **47,295 bytes**, including the
  system/user messages and model JSON/thinking options.
- Semantic base request body: **42,589 bytes**, measured with the normalized
  envelope string empty and a fixed 64-character digest placeholder. This is
  base overhead only, not a prediction or guarantee for the producer-dependent
  semantic request.

Fixed limits: catalog entries 64; arrays 64; candidate paragraphs 128;
strings 8,000 bytes; source body 20,000 bytes; normalized JSON 40,000 bytes.
Each `deepseek-flash` role retains request budget 1, maximum input 80,000 bytes,
maximum output 40,000 bytes, 6,000 output tokens, 45-second timeout, JSON mode,
and thinking disabled. No model cap is raised. Before the semantic call, the
existing runtime must measure and enforce the **complete actual request**
against 80,000 bytes. If the producer envelope makes it too large, semantic is
not called; no truncation, retry, or fallback is allowed. Thus this sizing does
not guarantee that an unknown producer result will fit.

#### Offline checks and repository code-state guard

Syntax compilation passed. Default offline execution passed the focused fake-
client route: one synthetic discovery request (47,295 bytes), one synthetic
semantic request (43,574 bytes), finalized in-memory audit, zero external
requests, and zero hypotheses. The facts-only zero-hypothesis result is an
offline structural fixture, not a model, semantic, or EI result. Source/model
payloads were not printed or persisted.

The runner's code-state guard keeps the script hash stable across a docs-only
protocol commit: registered baseline `6bcb031bb2993fefaf8b6758a6a3d96da7d4ac3d`
must be an ancestor of `HEAD`; the baseline-to-`HEAD` committed path set must
be entirely under `docs/`; and current worktree, index, and untracked paths
must also be docs-only. Consequently `src/`, `tests/`, and other non-document
paths must be clean. A synthetic subprocess-spy test passed nine cases covering
docs-only descendant acceptance and rejection of committed, worktree, staged,
and untracked source/test changes, plus a non-descendant baseline. It performed
no commit. The guard does not require changing the runner's pinned baseline or
rehashing it after a documentation commit.

This preregistration authorizes no invocation by itself. Old protocol records
remain unchanged. Cumulative source reservations remain eighteen; no source
request or model request was made here.
