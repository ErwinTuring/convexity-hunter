# IREN low-level semantic date calibration — 2026-10-02

Status: **PREPARED / OFFLINE CHECKS PASS / MODEL-ONLY NOT AUTHORIZED OR EXECUTED**.
This is a small external semantic calibration, not production behavior, a
product Grounder run, or investment analysis.

## Registered artifacts and frozen inputs

Run ID: `iren-semantic-calibration-20261002-b30fa95e91fb42fa81006251c3191175`.

- Runner: `/private/tmp/ch_iren_semantic_calibration_2026-10-02.py`; SHA-256
  `6a5c6457b01581dab10323d1ec1512009121d07740f4834aaafc8691f5c31af1`; mode
  `0600`.
- External preregistration: `/private/tmp/ch_iren_semantic_calibration_2026-10-02.prereg.json`;
  SHA-256 `dc33b303f4447f2084bb9d9b4f19cb0a6d051e27fe436cd2c3e2ce8d0574172c`;
  mode `0600`.
- Reused helper: `/private/tmp/ch_iren_transport_capacity_2026-10-02.py`;
  SHA-256 `6247e9e84313a0891bd37838ce1b268bfc479b38462256902e14696695241dbc`.
- Production guard: commit
  `46876fda3473f72e43671040529bc3427f467047`; src/tests manifest SHA-256
  `101a92a4efd2788072409f6d000453a0561175ab41e6465428472dcd8fc01c0d`.

The sole source is the retained SEC body
`/private/tmp/ch_grounder_source_snapshot_a8lfydaw/registered-body.utf8`,
9,423 bytes, SHA-256
`00ecc509846b657702081827db78a220b8ff51a9bacd19537339575e17ee6e29`.
Its review status remains `PENDING_BODY_REVIEW`. The separately Host-reviewed
date anchor is exact Unicode `[2603,2638)`, line 91:
`agreements, each dated May 29, 2026`, SHA-256
`9efb6189ebe4c80b6cf4a1672fe57503ae09b8181fc568f8cc59706e630f3fe8`.
This narrow anchor review does not claim whole-body review or source truth.
Source requests are zero. Preparation and offline checks make no network or
model requests; a separately authorized model-only execution may make one
semantic-verifier request under the bounds below.

## Calibration contract

The runner imports the hash-pinned capacity helper and uses the existing
evidence catalog, semantic verifier prompt/wire parser, and
`build_semantic_validation_receipt`. It does not copy the larger helper or
modify repository source/tests.

The Host constructs two synthetic observed-fact claims against the retained
body, both citing its exact catalog paragraph and each with an exact
`/claims/{i}/event_date` binding:

- `event_date_2026_05_29`: **supported** (golden expectation).
- `event_date_2026_05_28`: **contradicted** (golden expectation).

The envelope has no entities, dependencies, or hypotheses. One coverage item
is retained because `HostGrounderRunInput` requires at least one predeclared
subquestion; it asks only for the two date classifications. A syntactically
valid `unresolved` negative outcome is fail-closed and is never strict
classification PASS. Strict PASS requires both expected claim outcomes and
both corresponding field-binding outcomes.

Offline Host-receipt negative: the verifier fixture retains both binding
verdicts in the golden case. A second, separate fixture removes the
`/claims/0/event_date` binding from the envelope and its corresponding
verifier binding record, recomputes the envelope hash, and retains a supported
verdict for that claim. The v0.3 semantic parser must accept the aligned
remaining binding record; the existing Host receipt builder must then reject
the supported claim because its required date binding is absent. This tests a
Host-receipt gate, not malformed verifier binding identities.

The emitted partitions contain only static control IDs and counts. The
low-level synthetic receipt is not an authenticated same-run product receipt;
no Builder, Core, Event Intelligence, or product pipeline is invoked.
Rationales, raw source/model payloads, credential material, and exception
details are never emitted.

Offline fixture outcomes and receipt partitions are emitted only in
`offline_*` fields. The unprefixed live outcome fields remain empty/unknown
unless the actual verifier response parses and its Host receipt is built; a
model-call, parse, or receipt failure leaves them empty. An offline simulated
model-only failure checks that golden fixture outcomes do not leak into those
live fields.

## Bounds and authorization boundary

Default execution is offline-only and uses a fake transport. The separately
guarded model-only mode permits at most one existing semantic-role client
invocation: 6,000 tokens, 80,000 input bytes, 40,000 output bytes, 45 seconds,
JSON mode, thinking disabled. Configuration comes only from the existing
semantic-role resolver; no provider/model or configuration default is added.
The output's `semantic_client_complete_method_calls` is the `_MeteredClient.complete`
method-entry count only; it does not prove that a transport was entered or
succeeded. `semantic_call_attempts` records entry into the bounded `_call_once`
attempt after prerequisites, also not transport proof.
Source requests, producer calls, Core calls, Builder calls, retries, and
fallbacks are all zero. In this prepared/offline artifact, source requests and
actual model requests are zero; only a later explicitly authorized execution
can make the single bounded semantic-verifier request.

Before any model-only invocation, the runner requires the exact production
guard, this document committed in a docs-only descendant, a matching external
preregistration and runner hash, the full preregistration commit argument, and
`--main-authorized`. The flag is an operator assertion, not independent
authorization; Main's direct authorization and review remain required. The
one-shot marker is created with `O_EXCL` mode `0600` before the verifier call
and is never cleared or retried. No marker is created by preparation or
offline checks.

## Offline validation result

Ran:

```text
python3 -m ast /private/tmp/ch_iren_semantic_calibration_2026-10-02.py
python3 -B /private/tmp/ch_iren_semantic_calibration_2026-10-02.py
```

Both passed. The offline run reports one fake verifier transport and passes:

- the supported/contradicted golden controls and their Host receipt partitions;
- supported claim rejected by the Host receipt when its exact event-date
  binding is absent, while the matching verifier binding record is also absent;
- malformed verdict fail-closed;
- unresolved negative fail-closed, not strict classification PASS; and
- second request blocked by the one-call budget; and
- offline golden outcomes remain separate when a simulated model-only run
  fails closed.

No live/model/network call or real credential resolution occurred. No
production/test file, Git index, or commit was changed. Preparation itself
does not authorize or execute the future model-only mode.
