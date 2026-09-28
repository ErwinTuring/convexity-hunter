# Host Grounder Builder Contract v0.2 (Delta)

Status: **FROZEN / SUBSEQUENT_BUILD_READY**. This delta inherits
[Builder v0.1](host-grounder-builder-v0.1.md) unchanged except the Event
provenance and receipt-schema changes below. Production v0.1 remains unchanged.

## Deltas

For Event, `canonical_input_hash` is SHA-256 of the exact canonical
[`HostGrounderRunInput`](host-grounder-run-input-v0.1.md) payload, including
the original `UserEventInput` fields and predeclared ordered subquestions.
`run_id` is copied from `run_start`, carried on the immutable run record, and
excluded from the canonical payload/hash; runtime checks it against
`HostBuildContext.run_id` and checks `context.raw_input is run_input.user_input`.

In the inherited `SemanticValidationReceipt`, change only
`schema_version` from `semantic-validation-v0.1` to
`semantic-validation-v0.2`; all other receipt fields and Builder behavior are
unchanged. The low-level Builder API and EI/Core APIs do not change. This delta
does not implement or claim a v0.2 runtime or live Host run; future product
Event runtime must implement v0.2 after review.
