# IREN closed parser-check diagnostic preregistration — 2026-10-02

Status: **EXECUTED / SPENT — `DISCOVERY_CALL_FAILED`; failure stage/check null**.
This is a new independent attempt. It inherits mechanics only from the [10-01 transport
diagnostic](standalone-iren-transport-diagnostic-trial-2026-10-01.md) and its
[base diagnostic preregistration](standalone-iren-diagnostic-trial-2026-10-01.md);
their authorizations are spent and all prior runners, markers, registrations,
and receipts remain immutable.

## Registration

RunID: `iren-transport-check-model-only-20261002-cc929c9173de42a9bbd43b24e0a3f121`.

- Runner `/private/tmp/ch_iren_transport_check_diagnostic_2026-10-02.py`:
  48,790 bytes, mode 0600, SHA-256
  `a6025c4e58473ec94042ec82592dc1bd87e54a3446cd77a4e02e02e6dddca9ac`.
- Prereg `/private/tmp/ch_iren_transport_check_diagnostic_2026-10-02.prereg.json`:
  4,197 bytes, mode 0600, SHA-256
  `914e7091b95c8461b260d2a60f7d457c844f0e107b559a41c27c57ec7921c2f1`.
- Exact input runner `/private/tmp/ch_iren_transport_model_only_v0_2.py`:
  SHA-256 `4574866aa080f20295703acbe1623283f50239073d094c1c73a100e2c85daa43`.
- Reviewed transport helper SHA-256
  `ecbe186fd5e85c4fdbb0c93ede0b0b4569415b372dc8be80605615ab494fb9b8`.
- New exclusive marker:
  `/private/tmp/.iren-transport-check-model-only-20261002-cc929c9173de42a9bbd43b24e0a3f121.attempted`;
  claimed once by this execution, mode 0600, 8 bytes; retained and never cleared.

The delta is limited to the new identity/paths/marker, code-state pins, and a
sanitized `failure_check` report field. Emit it only from the exact
`HostGrounderRuntimeError` when its exact closed `failure_stage` is
`semantic_wire_parse`, and only for these exact labels:
`wire_decode`, `topshape`, `run_binding`, `catalog_validation`,
`producer_binding_alignment`, `evidence_ref_expansion`,
`internal_verdict_validation`. Otherwise it is null. Existing safe stage and
transport fields remain unchanged; no exception details or payloads are read.
The frozen contract is in [Host Grounder Context Preparation](host-grounder-context-preparation-v0.1.md).

## Inherited protocol and gates

Production code pin: `46876fda3473f72e43671040529bc3427f467047`; exact
`src/tests` manifest SHA-256:
`101a92a4efd2788072409f6d000453a0561175ab41e6465428472dcd8fc01c0d`.
No production or test files change. Source body/hash/retrieval/date anchor,
inputs and subquestions, prompts, `deepseek-flash`, v0.2 route, trusted Host
preparer, transport wrapper, and evidence gaps are inherited unchanged; no new
source, prompt tuning, credential resolution, live call, retry, or fallback.

Budgets remain one producer and at most one verifier; source 0; retry/fallback
0; catalog 32,768 bytes, 64 entries/array items, 128 paragraphs, 8,000-byte
strings; model input/output 80,000/40,000 bytes; 6,000 tokens and 45 seconds
per role; JSON mode on and thinking off. Retained source body is 9,423 bytes,
SHA-256 `00ecc509846b657702081827db78a220b8ff51a9bacd19537339575e17ee6e29`.
New-ID measurements: catalog 24,083 bytes (48 entries, 60 paragraphs, 12
nonunique, 0 overlong); full discovery request 48,493 bytes; semantic base
44,894 bytes; synthetic full semantic request 60,850 bytes. Actual verifier
request remains producer-dependent and must pass the unchanged 80,000-byte
guard.

Main's separate one-shot authorization and the preregistration-commit gate were
satisfied for this run: docs-only commit
`dea77fe566e3344997e6fa9373640bde472a3055` was pushed, and Main directly
authorized the exact runner invocation after independent safety review PASS.
Runner flags alone confer no authority; this record authorizes no further call.

## Offline validation

Runner passed with synthetic producer/verifier calls 1 each, external requests
0, and credential resolutions 0. The failure-stage/check suite passed 37 cases
(all seven accepted labels, invalid values/types/subclass, stage combinations,
and parser-path propagation); transport composition 6, prereg gate 8, code
guard 12, preparer 8, source-negative 2, and exclusive-marker 2. A focused AST
comparison found 22 of 24 original top-level functions identical; only the
diagnostic checks and report assembly changed, with one extraction helper
added. The model-only entry point and remaining functions are unchanged.

Main also ran the full regression at the pinned production baseline: 1,628
tests passed in 296.423 seconds. The existing urllib3/LibreSSL warning was
non-fatal. This is repository validation, not live Grounder acceptance.
Independent narrow runner/protocol safety review passed before registration.

## Authorized one-shot result — 2026-10-02

Exactly one invocation exited 1. It returned exact `HostGrounderRuntimeError`
code `DISCOVERY_CALL_FAILED`; `failure_stage=null` and `failure_check=null`.
Discovery calls/reserved: 1/1, elapsed 18.099 seconds, transport code
`TRUNCATED_RESPONSE`, HTTP status null. Token usage was not reported. Semantic
calls/reserved: 0/0; semantic transport fields null. Source calls 0 and
preparer calls 0. No producer counts or receipt were validated; claim,
hypothesis, binding and coverage counts and all semantic partitions remain
null. No submission or EI result exists.

Exact sanitized stdout is retained at
`/private/tmp/ch_iren_transport_check_diagnostic_2026-10-02.result.json`, mode
0600, 2,585 bytes, SHA-256
`c8dd940a1ccd40fd56952bf8e95021b637148abb85f185f4ffff350f5cefafca`. No raw
response was retained. This attempt is spent; no retry or fallback.

Next lawful step, offline only: inspect the existing `finish_reason="length"`
mapping to `TRUNCATED_RESPONSE` in `host_model.py` and its existing
`test_tool_calls_refusal_and_length_stop_are_rejected` case in
`tests/test_host_model.py`. Do not infer a response body, tune prompts, or make
another call.

## Offline finding and next capacity boundary

The exact existing fake-transport length-stop test passed. The mapping rejects
the response before content/usage parsing; it is correct, not an implementation
defect. The safe code establishes a provider length-stop signal, not which
limit caused it or whether 6,000 completion tokens were consumed.

The 6,000-token cap is this preregistered run's operational bound, not a global
contract or user account budget. Repository workflow delegates ordinary
execution to Main; its portfolio risk policy is separate from model diagnostic
bounds. No aggregate API monetary/token ceiling or prohibition on a fresh
bounded capacity registration was found. Main chooses a new, independently
registered capacity probe: producer at most 8,000 tokens, verifier at most
6,000, one call each, all byte/parser limits and prompts unchanged. This is
not permission to reuse this spent protocol or increase application defaults.
No monetary charge is estimated, and completion is not guaranteed.

The [official Chat Completions documentation](https://api-docs.deepseek.com/api/create-chat-completion/)
checked 2026-10-02 documents an 8K non-thinking default and describes length
stops as token/context-limit events. It does not prove which limit applied to
this account's failed request. Any new invocation still requires reviewed
artifacts, committed preregistration and separate Main execution authorization.
