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

Stop blind provider calls. `PRODUCER_ENVELOPE_INVALID` covers schema parsing,
stage/run identity, ordered coverage, and canonical-size checks; the exact
rejection gate is not yet known, and the payload is no longer available. Next,
prepare an offline DTO diagnostic; after that, at most one separately bounded
one-shot may identify the rejection gate. Do not treat normal model transport
completion as Grounder or EI acceptance.
