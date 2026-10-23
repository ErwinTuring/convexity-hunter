# Host Semantic Validation Contract v0.2 (Delta)

Status: **FROZEN / SUBSEQUENT_BUILD_READY**. This delta inherits
[Semantic Validation v0.1](host-grounder-semantic-validation-v0.1.md)
unchanged except the Event provenance and receipt-schema changes below.
Production v0.1 remains unchanged.

## Deltas

For Event, `canonical_input_hash` is SHA-256 of the exact canonical
[`HostGrounderRunInput`](host-grounder-run-input-v0.1.md) payload: the original
`UserEventInput` fields plus its nonempty, unique, predeclared ordered
`(subquestion_id, text)` records. `run_id` is copied from `run_start`, carried
on the immutable run record, excluded from canonical bytes, and checked against
`HostBuildContext.run_id`; the exact `raw_input` object identity and context
hash are also checked before calls.

The Host receipt changes only its `schema_version` to
`semantic-validation-v0.2`; all other fields, gates, and semantic-assessment
rules remain inherited from v0.1. Future Event runtime must consume this input
record and construct the v0.2 receipt internally in the same run. No v0.2
runtime or live Host run is implemented or claimed here.

## Payload-free rejection projection clarification — 2026-10-23

Status: IMPLEMENTED / independent targeted REVIEW PASS after bounded read-only
preflight. Semantic 27, Store 59, Event 63 and one service save/restart test
pass (150 total); public API, compileall and diff checks pass. No full-suite
rerun is claimed for this diagnostic-only addition; deployment/live validation
are next. The
historical freeze above is unchanged. This addition concerns the current
default bound-object route (verifier wire v0.4 / prompt v0.9 / private runtime
v0.10), not semantic acceptance or the receipt schema.

`HYPOTHESIS_REJECTED_BY_VALIDATOR` means the hypothesis is absent from the
receipt's verified partition. It can follow a direct verifier judgment,
unsupported exact references/field bindings, or Host dependency checks. It
does not by itself prove that the model rejected an economic mechanism.
Existing offline fixtures demonstrate a supported hypothesis rejected by
dependency propagation. Run `fe638c4b` retains only aggregate diagnostic counts;
its finer cause is UNKNOWN and must not be reconstructed retrospectively.

Collect a private, immutable run-local projection at the actual semantic gate,
before free-text reasons are concatenated. For each rejected claim, hypothesis
or field binding, retain only its `kind`, exact envelope-array `index`, closed
`verifier_outcome`, and sorted unique closed `checks`. Distinguish direct
unresolved/contradicted judgments, exact-reference failure, required binding,
claim dependency closure/cycle, invalid hypothesis roots, hypothesis dependency
closure, and supporting-source checks. Categories must come from the executed
checks, never from parsing model rationales, exception text or receipt reasons.

Canonical kind order is `claim`, `hypothesis`, `field_binding`, with ascending
index inside each kind. The exact closed check vocabulary is
`verifier_unresolved`, `verifier_contradicted`, `missing_exact_reference`,
`required_field_binding`, `dependency_closure`, `dependency_cycle`,
`hypothesis_roots_invalid`, `hypothesis_dependency_closure`, and
`hypothesis_support_source`. Preserve all triggered categories, not just the
first. Unsupported or missing metadata is not synthesized from reason text.

Object identity is the existing run ID and normalized-envelope SHA-256 plus
kind/index. Do not persist model-authored object IDs, hypothesis text,
rationales, quotes, evidence refs, registered bodies, raw responses, credentials
or account data. The original in-memory receipt and exact Builder diagnostics
remain unchanged; this durable projection does not retain the original prose
reason and is not itself factual evidence. Coverage retains its existing audit.

Only the actual default Event recipe's results carrying the complete bound
private projection use stage-outcome v0.5 (including the submission variant).
Wire/prompt version pairing alone is not proof of default-recipe identity:
explicit custom-preparer paths retain their prior stage behavior and gain no
invented fact anchor. Retain an empty
array when no semantic objects were rejected. At save, validate closed shape,
exact types, index ranges/order/uniqueness, allowed categories, exact rejected
partition membership and run/envelope provenance against the same-run receipt
and snapshot. Readback validates the stored closed projection, bounds and
existing integrity/provenance rules; it does not reconstruct an unretained
receipt or independently reverify source semantics. Reject malformed data
rather than silently dropping it. Existing v0.1-v0.4 records
remain readable without modification or invented details. This adds no table,
general diagnostic framework or public callable/record signature.

The public receipt builder signature, receipt fields/bytes, verification
partitions, prompts, model calls, budgets/retries, EI/Core, Direct and all
explicit legacy routes remain unchanged. Preserve golden valid-receipt and
legacy-stage checks, distinguish supported-but-dependency-rejected from direct
unresolved in focused fixtures, test malformed/injected metadata and private
text exclusion, then independently review the diff. Any subsequent normal
Event validation is one fresh guarded run under existing budgets, not a
historical replay or semantic reroll. EI ACCEPTED must immediately continue
through the existing Futu/Core path; otherwise preserve the exact refusal.
