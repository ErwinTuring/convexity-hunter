# Host Grounder Context Preparation Contract v0.1

Status: **FROZEN / IMPLEMENTED — INTERNAL OPT-IN ROUTE ONLY**.
Main accepted independent contract and implementation review, including fixes
for tuple-container identity and returned-context constructor bypass. The
catalog runtime v0.2 is implemented; legacy routes remain unchanged. No live
product Grounder or EI acceptance follows from this implementation.

## Scope and compatibility

Reuse the catalog, producer/verifier wires, v0.2 receipt, `HostBuildContext`,
and Builder; add no model role, wire field, source request, retry, or EI change.
Catalog v0.1 and Builder/EI APIs stay unchanged. This is experiment composition,
not product integration or a source-truth guarantee.

## Preparer interface

The v0.2 route requires an explicit trusted Host preparer; no default exists.
Proposed exact interface:

```python
def prepare_host_build_context(
    snapshot: ValidatedEnvelopeSnapshot,
    validated_receipt: Mapping[str, object],
    original_context: HostBuildContext,
) -> HostBuildContext: ...
```

`ValidatedEnvelopeSnapshot` is the existing frozen type (`canonical_bytes`,
`envelope_hash`). No validated-receipt wrapper exists: pass the checked receipt
as `MappingProxyType(dict(receipt))` (values are scalars/tuples). The preparer
may parse snapshot bytes with the existing parser/bounds, never a mutable envelope.

## Required call order

1. Before calls, validate/freeze run-input identity and the exact source
   registry. Require a callable preparer before any model call; otherwise fail.
2. Run existing producer/verifier once each and construct the v0.2 receipt.
3. Explicitly call `validate_semantic_validation_receipt` with the run ID,
   input hash, ordered request IDs, frozen bodies, existing limits, and
   `expected_schema_version="semantic-validation-v0.2"`. It returns the
   immutable snapshot bound to the receipt and source hashes. Only on success,
   capture pre-call snapshot/context values, then call the preparer exactly
   once with the three interface arguments.
4. Revalidate the snapshot hash and original context against captured values
   (not aliases); recheck run-input identity and receipt binding from captured
   canonical bytes, receipt, and source snapshot. Guard the result, decode the
   captured bytes into a fresh envelope dict, then invoke the existing v0.2
   Builder, which retains its own receipt validation.

The preparer cannot mutate the verified envelope or receipt. A preparer error,
wrong return type, or identity-guard failure produces a sanitized Host failure;
do not expose exception text, payloads, arguments, or locals. Do not call
Builder/EI, retry, or make further model/source calls after such a failure.

## Returned-context identity guard

Capture raw-input identity; context scalar values; source keys, record identities
and metadata; existing bindings; and caller-policy identity before callback.
Afterward recheck the original against those saved values. The result is exact
type `HostBuildContext`, with `raw_input is` the captured object and
`run_input.user_input`. Run/hash, observed time, submission/event/producer IDs
and versions, caller-policy identity, and source keys/records/body/hash/locator/
retrieval time/title/publication time stay unchanged. Only the three fields
below may differ; the returned context is immutable for its Builder call.

## Permitted preparation and unknowns

- Snapshot IDs are lookup addresses, never facts or authority. Do not hardcode
  fixture IDs, rename IDs, or bind IDs absent from the snapshot/validated receipt.
- `event_description_binding` may name only a verified claim ID whose retained
  claim is a source-backed observed fact; existing Builder closure rules apply.
  Preserve an existing non-`None` value exactly; fill only when absent.
- Add an underlying entry only for a verified hypothesis ID and verified symbol,
  after independent Host listing evidence establishes the exact `UnderlyingKey`.
  Model text cannot establish listing identity or currency; unknown/conflicting
  evidence means no entry.
- Preserve an existing `event_date_range` by object identity. Fill only when
  absent, from independent Host evidence and methodology. Never derive it from
  model dates, `UserEventInput.event_date`, publication time, or reassessment.
  Do not infer impact windows or deadlines. Existing source-backed reassessment
  rules remain unchanged; do not create or roll deadlines forward.
- Existing underlying-map entries are fill-only: retain each exact pair by
  value and the same `UnderlyingKey` and evidence-reference objects; never
  replace/remove. Tuple containers may be reconstructed by `HostBuildContext`.
  Add only absent keys meeting the independent-evidence rule above. Preserve
  caller-policy provenance; missing evidence stays missing. Receipt validation
  does not prove source truth; source authority remains a trusted Host duty.

## Minimal integration shape and attack cases

The implementation adds only the explicit `run_host_grounder_same_run_evidence_catalog_v0_2` path
with a required preparer; leave v0.1 unchanged. The current v0.1 function
snapshots context before discovery and passes it unchanged to Builder, so it
has no post-verification hook. The new v0.2 route is opt-in; v0.1 does not use it.

Attack cases: absent preparer fails before calls; zero calls on validation
failure/exactly one on success; receipt/run/hash/coverage/body mismatch stops;
`object.__setattr__` mutation is caught by saved-value/hash revalidation;
callback cannot alter Builder's captured envelope/receipt; replacing existing
bindings or binding fixture/unknown/rejected IDs fails; model-only
symbol/currency/date/deadline cannot create Host evidence; missing listing proof
stays unresolved; preparer errors are sanitized; Builder/EI stop; v0.1 unchanged.

## Frozen failure semantics

The callable signature, route name, and guards above are frozen. Missing or
non-callable configuration fails before calls with
`HOST_CONTEXT_PREPARER_INVALID`; callback exceptions, return-type and guard
failures use `HOST_CONTEXT_PREPARATION_REJECTED`. Invalid receipts retain
`SEMANTIC_VERDICT_REJECTED`. No exception details are emitted. Host supplies
existing listing/fact evidence; no new evidence type or provider is defined.

## Sanitized failure-stage extension

Status: **FROZEN / IMPLEMENTED** after bounded read-only preflight and
independent diff review. Thirteen focused tests and 104 related tests,
compileall and diff checks passed. This is operation-level observability only;
the full suite was not rerun for this behavior-preserving extension.

Freeze `HostGrounderRuntimeError(code, *, failure_stage=None)` with exactly
`None`, `"semantic_wire_parse"`, `"semantic_receipt_construction"`, or
`"semantic_receipt_validation"` as permitted values. Reject other values with
a static error. Populate non-null stages only in the explicit catalog v0.2
route when that exact operation fails. Legacy routes retain `None`.

Keep `.code`, `.args`, `str`, existing `repr` and suppressed exception chaining
unchanged. Stage labels contain no exception text, payloads, model assertions,
identifiers or source data. They neither change fail-closed behavior nor
authenticate the verifier. Split the existing combined parser/construction
catch and label the separate pre-preparer receipt-validation catch; perform
no extra calls or retries. A stage says where rejection occurred, not why.
The spent IREN trial's unexposed stage remains unknown retrospectively.

## Closed parser-check diagnostic — successor contract

Status: FROZEN / IMPLEMENTED — INTERNAL OPT-IN ROUTE ONLY. Independent
contract and implementation reviews passed. Sixteen focused tests (both
invocation patterns), 107 related tests, compileall and diff checks passed.
No full-suite rerun or live call belongs to this diagnostic-only extension;
the last 1,622-test full pass predates both diagnostic extensions.
Read-only preflight found no demonstrable prompt/parser contradiction. Eight
synthetic probes respected the existing schema. The new live trial located
`semantic_wire_parse`, not its exact failed check; do not infer that check
retrospectively or tune prompts to force acceptance.

Extend `HostGrounderRuntimeError` with keyword-only `failure_check=None`.
Permit only `None` or these exact static strings; non-null requires
`failure_stage="semantic_wire_parse"`:

| Check | Existing operations, in unchanged execution order |
| --- | --- |
| `wire_decode` | Limit validation and JSON decoding |
| `topshape` | Closed top-level keys and schema version |
| `run_binding` | Exact wire run ID |
| `catalog_validation` | Registered source/catalog validation |
| `producer_binding_alignment` | Producer ID tuple, binding count/index and supported-ref alignment |
| `evidence_ref_expansion` | Section/ref shape, bounds, duplicates, unknown IDs and catalog expansion |
| `internal_verdict_validation` | Normalization/cap, internal verdict parser and final normalized bytes |

These labels identify operations, never factual truth or detailed causes.
Preserve `.code`, `.args`, `str`, existing `repr` and suppressed chaining.
Receipt-construction/validation failures have no check label. Legacy routes
retain `None`; accepted/rejected inputs and first-failure precedence stay
unchanged. No exception text, args, identifiers, payloads or arbitrary values
are read into diagnostics.

Keep the public catalog verdict parser's signature and bytes return unchanged.
Move its current body to one private helper with an optional tiny private
progress holder, assigning literal labels before existing check groups. The
helper must not catch/translate/store exceptions or invoke callbacks. The
public wrapper delegates without a holder. Only opt-in runtime v0.2 creates a
holder and calls the private helper; its existing catch copies the closed
label into the sanitized error. No generic telemetry facility or wire change.

Authorized BUILD scope after review/freeze: catalog module, runtime module and
focused tests only. Tests cover each category, first-failure precedence,
identical valid public/diagnostic bytes, legacy errors, illegal stage/check
combinations, no payload leakage, and zero preparer/Builder calls on failure.
No model/source requests, live trials, retries or prompt changes are part of
this work unit. This contract does not reopen any spent protocol.

Offline tests must inject each failure, prove zero preparer/Builder calls,
preserve legacy stage `None` and error representations, and reject arbitrary
stage values. No fresh live experiment is part of this extension.
