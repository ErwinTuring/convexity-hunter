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
