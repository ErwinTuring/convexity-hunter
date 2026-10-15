# Grounder rejection attribution — 2026-10-15

Status: released once after offline tests/review; result INCONCLUSIVE. No
further live request is permitted within this unit. This is a single-input diagnostic work unit,
not a third arm/repair/replay of the closed
[source control](grounder-mechanism-control-2026-10-15.md).

## Demonstrated gap and bounded correction

The production semantic converter already emits closed rejection-check counts
from `_emit_rejection_checks`. The previous external experiment disabled logging
and retained only coarse Builder codes, losing these finer distinctions. Those
old counts cannot be recovered. This is a demonstrated external recording gap,
not evidence that production acceptance is wrong.

An isolated, single-thread lab collector temporarily captures only that existing
emitter's closed numeric dictionary and restores the original function in
`finally`. Production files, receipt, reference checks, prompts and decisions
are unchanged. Do not use this process-global laboratory hook in the Host.
Unknown keys/types must not be stringified or leaked. Collector failure must not
alter parser outcomes; an incomplete/missing capture is not a zero-rejection
result. Preserve completion count separately from category counts.

Fixed categories: dependency_closure, dependency_cycle, hypothesis_roots,
hypothesis_support_source, missing_exact_reference, required_field_binding,
unknown, verifier_contradicted, verifier_unresolved. These count triggered
checks across object types, not unique rejected claims or economic causes.
No free-text rationales, model/source/subject IDs, source/model bodies,
credentials or account data may be serialized or logged. A Host-generated
run UUID may identify the diagnostic execution, never a model-supplied ID.
Such payload details are not needed to distinguish these checks.

## One independent release, no retries

After offline tests and independent review, Main alone may release one guarded
single-input run under the user's standing bounded-validation authorization.
Use the exact IREN official URL and open question from the closed control,
the current existing external configuration/model, runtime v0.6/prompt v0.7,
and unknown-preserving context. No B arm, prefilled identity/date authority,
listing enrichment, origin admission, Futu, Core or Host archive insertion.
The historical filing is not proof of current financing status.

Reuse the archived script's exact question, verified before release by SHA-256
`97a5d46ad745219e3eebe7edcee2d24fe564012476b37f1b5ccd497e089839be`:

> What source-backed economic transmission, if any, does this filing describe in connection with the disclosed financing? Distinguish reported facts, interpretations, and unknowns; do not infer real-world absence beyond this source.

The archived helper SHA-256 must match
`584983b8e77a6ff86a0d9273cd53b27356cf27b6e98d015cb96009f8ad026c2f`.
It calls `run_host_grounder_same_run_evidence_catalog_v0_6`; the selected
discovery/semantic prompt identifiers remain their existing v0.7 values.
Offline checks must verify those identities, not silently select a successor.

Maximum: one Tavily Basic Extract request/one-credit reservation and one
discovery plus one semantic request. No retry for format, transport, recording
failure, unhelpful output or acceptance. Use a new dated O_EXCL guard, never
reopen old guards. Keep source/question hashes and producer/verified/projected
counts separately. Save sanitized output privately and atomically before a
short stdout result. A failed run is recorded as failed, never replaced.

This is explicitly a third source acquisition opportunity across the prior
two-round control plus this new unit: cumulative ceilings become three source
requests/three credits/ten model-request reservations, not confirmed charges.
It is not a claim that the old two-round cap has remained unchanged or that
new outputs explain a specific historical model response.

## Interpretation fixed before release

Nonzero `missing_exact_reference` distinguishes exact-reference rejection from
the verifier's unresolved/contradicted assessments. Required binding and closure
checks can amplify an earlier failure; aggregates are not necessarily root
causes. An unresolved assessment is fallible and not proof the source lacks a
fact; supported assessments alone are not external truth. Counts do not settle
substantive entailment or justify changing a gate. New model output is not
historical replay; compare stages, not model improvement.

The result must report which attribution layer is actually established and
which remains unknown. No mandatory positive hypothesis, EI ACCEPTED target,
production patch or further live run follows merely from low output. If a
concrete implementation defect is independently established, fix only that
defect with proportional review/tests in a separate implementation step.

## Offline preparation evidence

The external collector and single-arm runner live in
`/Users/erwinlee/convexity-hunter/research/grounder-rejection-audit-2026-10-15/`.
Sixteen focused synthetic tests passed, covering unchanged receipts, existing
rejection branches, disabled logging, hostile values, exception restoration,
thread/nested interference, safe projection and unknown reservation counts.
Direct `--check` passed without network, credential/config loading or guard
consumption. No production file or repository test was changed. Independent
review identified an entry-cleanup gap; the collector now restores the emitter
even if entry fails after installation, and requires a closed/complete capture.

Pre-release SHA-256 identities:

- collector: `dfd6aa5be49df97878f2e0f278e103393e63bb29a11b0fe758372b687c8b2a9d`
- runner: `536a777712b92dcaa379508ee0b06ed60b67f437aacefd7e9b97a4dfa2c6e32b`
- tests: `76df9de038f18a502459ff4c1602b2ac2eb677cb508a79e6a13561a834c8e95d`

Final independent script review passed, including the targeted fixes. The
prepared script was unreleased when these identities were recorded; synthetic
tests do not prove live attribution. The subsequent result is recorded below.

## Sole real execution — INCONCLUSIVE

Main released the reviewed script once. Runtime exited 2 and safely saved the
complete derived summary before short stdout output; this is a complete
recording of an inconclusive execution, not a complete semantic assessment.

- Host-generated diagnostic run: `29ae8ae7-9a92-4a8d-8ee6-9c2252b0951e`.
- Source request/credit reservations: 1/1; discovery/semantic reservations: 1/1.
- Model total: 2, KNOWN reservations, not confirmed provider billing or success.
- Source-body and question hashes match the earlier control's retained hashes.
- Runtime: INCONCLUSIVE / HOST_GROUNDER_RUNTIME_REJECTED.
- Emitter calls/completions: 0/0; capture state NOT_CAPTURED; no collection,
  thread or emitter-replacement error was recorded.
- Semantic receipt completion was NOT_OBSERVED. Zero-filled category counters
  are **not observed zero rejections** and cannot identify a rejection cause.
- Producer, verified, projected and Builder counts are null/unavailable, not 0.
  EI was not assessed. Listing enrichment/origin admission and Core were NOT_RUN.

Safe summary:
`/Users/erwinlee/convexity-hunter/research/grounder-rejection-audit-2026-10-15/capture-414598f3d72a49bbae8ed0f12a17f930/summary.json`.
SHA-256: `e36d4a558bd548c2f3c24796048c620033115628f0127085b2bbe3a430598bf5`.
The private `.single-arm-release-once` guard is spent. Released collector,
runner and tests were additionally preserved in `released-536a7777/`; do not
modify them or replay the guard. No raw body, model rationale or credential
was saved. Cumulative reservations across the closed control and this unit
are 3 source requests/3 credits/10 model requests, not confirmed charges.

The inherited `_one_arm` catches HostGrounderRuntimeError and returns only the
generic runtime reason, discarding its existing code/stage/check attributes.
This is a demonstrated external-wrapper observability limitation. It does not
identify this run's precise operation, prove a production defect or recover
the earlier A rejection causes. In particular, a reserved semantic request is
not proof of a successful response or malformed model JSON.

The code provides one narrower bound without another call: client initialization
does not consume a request; the semantic reservation shows that role was
entered. The rejection emitter is invoked after successful semantic receipt
validation, before context preparation/Builder. With no observed emitter call
or collector error, the retained evidence bounds this attempt to the segment
from semantic-client reservation to receipt completion, not source extraction
or a validated economic abstention. Reservation precedes credential resolution
and transport; it does not prove an HTTP request was sent or a response received.
The capture cannot distinguish local credential/request preparation, transport,
response validation, wire parsing or receipt construction within that segment. This
new technical failure must not be substituted for the earlier A's completed
receipt/rejected-claim result.

No retry, second input, changed model/prompt or production fix followed. Only
offline preservation of the existing closed runtime-error markers may be
prepared next; it must not be described as recovery of the lost live markers.

## Post-run offline hardening, not a new release

Prepared `runtime_failure_capture.py` and its three passing focused tests in
the same private research directory. The isolated wrapper observes only the
existing allowlisted runtime code/stage/check before the inherited helper
catches the exception, re-raises the exact same exception and restores the
runtime function afterward. It never parses exception/rationale text, forwards
no payload to logs and adds no provider call. Unknown metadata remains absent.
Main inspected this small helper; the real-result interpretation above was
independently reviewed. This helper has no release command and was not wired
into or used to rerun the spent script. It is not a production deployment,
retroactive attribution, or live proof of the hardening.

- helper SHA-256: `c79414ddac7b2b868d137c61ab5d033fb4b1fbc57ae5d962b29936ac0ac4e345`
- tests SHA-256: `14a4d96c79e51e19ffeab080fade6b355d99c4b0ca40773022ff56bddd3a4bb4`

Repository changes are documentation only; new local-link/fence checks and
`git diff --check` passed. The 16 pre-release and three post-run tests are
offline synthetic evidence, not a new full regression or successful product
closure. Production remains unchanged; no acceptance/prompt change or new
positive World/Event-to-Core result is justified by this unit.
