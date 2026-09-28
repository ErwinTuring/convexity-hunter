# Host Grounder Run Input Contract v0.1

Status: **FROZEN / SUBSEQUENT_BUILD_READY**. This narrow pre-live contract defines Event run-input
provenance; it is not implementation, live-run evidence, or call authorization.

## Immutable Event run input

Before any external source or model call, Host freezes an immutable
`HostGrounderRunInput` containing the exact original `UserEventInput` object
(retained by identity, not copied) and a nonempty ordered tuple of immutable
`(subquestion_id, text)` records. IDs and text are nonempty strings; IDs are
unique. Preserve exact strings and tuple order without trimming, normalization,
rewriting, reordering, deduplication, or inference. The predeclared plan is the
only question set; model output cannot add, remove, or replace questions.
World input remains opaque and deferred.

`HostGrounderRunInput.run_id` is copied from the Host `run_start` record. It is
bound to the immutable record but omitted from canonical JSON and excluded from
the hash; runtime compares it with `HostBuildContext.run_id`, which is bound to
the same `run_start`. Canonical payload is exactly:

```json
{
  "mode": "event",
  "schema_version": "host-grounder-run-input-v0.1",
  "subquestions": [{"subquestion_id": "...", "text": "..."}],
  "user_input": {
    "description": "...",
    "event_date": "YYYY-MM-DD",
    "provisional_symbols": ["..."],
    "source_locators": ["..."]
  }
}
```

Copy the exact description, symbol/locator arrays and order from that same
`UserEventInput`; preserve allowed duplicates. Encode `event_date` as ISO
`YYYY-MM-DD` or JSON `null`. `source_locators` are untrusted hints: never
dereference them locally; only the bounded source client may use them after its
public-URL validation. The payload excludes `run_id`, fetched body registry,
and any model-generated plan.

## Encoding, bounds, and identity

Canonical bytes are strict UTF-8 of Python
`json.dumps(payload, sort_keys=True, separators=(",", ":"),
ensure_ascii=False, allow_nan=False)`, with no trailing newline. Hash those
bytes using lowercase SHA-256. Key sorting does not reorder arrays; no Unicode
normalization or field rewriting is allowed.

Host configuration supplies and records positive `max_run_input_bytes`,
`max_string_bytes`, and `max_array_items`; the caller/user and model cannot
choose or raise them. Every string and array must fit its bound, canonical
bytes must fit `max_run_input_bytes`, and complete model requests must fit each
role's configured byte limit. Missing/exceeded bounds fail closed before calls;
no clipping, truncation, extension, or fallback.

The runtime derives canonical JSON, hash, ordered IDs and text from this one
record, then verifies `context.run_id`, `context.raw_input is
run_input.user_input`, and `context.canonical_input_hash` against it before
using context or making calls. Mismatch fails closed. The producer's ordered
coverage IDs must equal the complete predeclared ID tuple; Host binds the
semantic stage. Extra, missing, duplicate, or reordered IDs fail closed.

The product Event runtime requires at least one valid subquestion. The
low-level Builder and EI/Core APIs remain unchanged; the low-level schema
parser may continue accepting empty coverage for structural/synthetic fixtures.

## Pre-live amendment and compatibility

This input contract does not alter production v0.1 behavior. Future Event
runtime must use [Builder v0.2](host-grounder-builder-v0.2.md) and [Semantic
Validation v0.2](host-grounder-semantic-validation-v0.2.md); they define the
whole-record hash and v0.2 receipt schema.
There is no v0.2 runtime or live Host run. Arbitrary existing test hashes stay
structural fixtures, not provenance authority, and are not migrated.

Required later golden tests independently pin canonical UTF-8 bytes and
SHA-256; cover Unicode, date/null, preserved arrays/order, run ID excluded from
hash, and identity/hash mismatch before calls. Also reject empty/duplicate IDs,
empty text, bound overflow, and producer coverage divergence, while preserving
empty low-level structural fixtures. Host-configured, recorded positive numeric
bounds are adequate; their exact values are runtime configuration, not defaults
implied by this contract.
