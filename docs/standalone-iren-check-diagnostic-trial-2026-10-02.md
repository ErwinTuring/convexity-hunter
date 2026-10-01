# IREN closed parser-check diagnostic preregistration — 2026-10-02

Status: **PREPARED / NOT EXECUTED / NOT AUTHORIZED**. This is a new
independent attempt. It inherits mechanics only from the [10-01 transport
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
  absent during preparation; future claim uses `O_CREAT|O_EXCL`, mode 0600,
  never clear or retry.

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

No invocation is authorized here. After independent delta review, this
docs-only preregistration must be committed/pushed; a distinct descendant
prereg commit must bind this RunID and both hashes above. Main's separate,
direct one-shot authorization bound to that commit remains required. Runner
flags alone confer no authority. This preparation makes no commit or call.

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
