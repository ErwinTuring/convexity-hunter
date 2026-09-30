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

Stop increasing token/time caps. The next step is an offline prompt/output-
boundary audit, not another live call. These transport outcomes establish no
product success or semantic correctness.
