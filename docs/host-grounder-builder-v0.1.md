# Host Grounder Builder Contract v0.1

Status: **FROZEN / BUILDER_BUILD_READY** after independent Tier-A review and
targeted re-review. This freezes one deterministic translation boundary only;
it does not claim a production or semantically verified Grounder.

## Scope and authorities

The builder translates one structurally valid `ModelOutputEnvelope` into at
most one existing `EventIntelligenceSubmission`, plus Host sidecars retaining
coverage and validation evidence. It performs no source retrieval, factual
verification, model call, user interaction, EI assessment, Core call, or
persistence. It is not itself a semantic Grounder.

The Host DTO rules in the
[MVP architecture](standalone-mvp-architecture-v0.1.md) remain the untrusted
wire boundary. EI types and acceptance remain authoritative in
[`event_intelligence.py`](../src/convexity_hunter/event_intelligence.py); this
contract adds no EI fields, issue codes, or acceptance rules. The semantic
verification steps remain separate as described in the
[Grounder verification design](event-grounder-semantic-verification-design-v0.1.md).

## Explicit build context

`HostBuildContext` is programmatic, caller/Host supplied, immutable for one
build, and never populated from model output. It contains:

| Value | Binding rule |
| --- | --- |
| `raw_input` | Retain the exact original object; result lineage must satisfy `result.raw_input is context.raw_input`. Never reconstruct or compare by value. |
| `submission_id`, `event_id`, producer ID/version | Exact Host-assigned identifiers. One build targets one event ID; multi-event envelopes must be split by the caller, never merged here. |
| `observed_at` | Required aware datetime supplied by the Host. Naive or missing values reject the context; normalize only as the EI constructor does. It is not source publication time or event time. |
| `source_bodies` | Exact registry keyed by source ID; each entry contains the fetched body, SHA-256 of its exact UTF-8 bytes, final locator, retrieval time, and optional title/publication time. The Host verifies the body hash before building; publication time may remain unknown. No body or metadata may be fetched or inferred by the builder. |
| `run_id`, `canonical_input_hash` | Exact values from the immutable Host `run_start` record. The hash is of the canonical serialized original input, not Python `id()`; both bind the durable submission/validation sidecars to that run. |
| `event_description_binding` | Optional exact ID of one semantically verified, source-backed observed-fact claim whose unchanged text becomes `event_description`. Otherwise `None`; user intent and model summary stay in the input/DTO sidecar, not as verified event description. |
| `event_date_range` | Optional independently evidenced `MethodologizedDateRange`; preserve as supplied, including a legal partial range. It is not derived from claim dates. |
| `underlying_bindings` | Exact mapping `(hypothesis_id, underlying_symbol) -> (UnderlyingKey, evidence reference)`; the Host verifies the listing identity (`symbol`, MIC, security type, currency) against a readable authoritative listing/provider reference, independently of model text. Tuple-exact lookup only; absent proof maps to `None` with a diagnostic. |
| `caller_policy_provenance` | Optional Host record of an explicit caller authorization: run/input identity key, exact reassessment date and rationale, and authorization source. It cannot originate in model output or be inferred from a deadline. If absent or mismatched, retain the DTO request as unresolved and omit the reassessment. |

The builder does not pause for a case-level user checkpoint. Missing caller
policy provenance means no caller-policy reassessment is constructed.

## Preconditions and result

The caller first performs the architecture's strict JSON/schema validation
(including exact version/stage, closed fields, duplicate-key rejection, and
configured bounds). A separate semantic validator then evaluates the exact
envelope against the exact context and source bodies. Its result must be bound
to those inputs and distinguish invalid evidence from valid-but-unresolved
coverage. JSON validity, substring presence, and DTO status labels are not
semantic validation.

The builder accepts only the structurally validated envelope and a semantic
validation receipt bound to its canonical envelope hash, the `run_id`, and
the exact `(source_id, body_hash)` registry. The receipt identifies verified
and rejected claim IDs and verified field bindings; model-authored status is
never the receipt. It returns a `HostBuildResult` containing the exact
raw-input reference, optional typed submission, the original coverage and
field-binding sidecars, and the semantic-validation record. Coverage remains
keyed to the original request; acceptance of one hypothesis never upgrades
request-wide coverage. No submission is emitted when the registry contains
no readable source body or when no non-placeholder hypothesis has a
source-backed claim closure. In those cases retain a Host diagnostic and stop
before EI/Core; never manufacture an empty or placeholder submission. A genuine
but incomplete hypothesis may produce a legal partial EI submission and be
assessed normally.

Semantic validation may retain `unresolved` or `contradicted` coverage and
produce EI-incomplete submissions. Projection is deterministic: include a
claim only if its quote localization, source body, semantic support, and all
transitive dependencies are verified. Include a hypothesis only if every
declared supporting, contradicting, and reassessment-basis claim survives that
closure and every asserted factual/temporal field passes its applicable check.
An unverified provisional underlying symbol is the narrow exception: it maps
to `None` with an explicit diagnostic and cannot yield EI ACCEPTED. An excluded
claim/hypothesis remains unchanged in the DTO and receives an explicit reason
in the receipt; neither its text nor IDs are relabeled, silently dropped, or
used as EI evidence. Unrelated verified hypotheses survive. If none survives,
emit no submission and stop before EI/Core. A surviving hypothesis may still
lack optional EI fields and be assessed as INCOMPLETE.

## Deterministic mapping

- A claim's `quote` must occur **exactly once** in the exact registered body;
  record its Unicode-codepoint half-open span and body hash in the sidecar.
  Zero or repeated occurrences make localization unresolved and exclude that
  claim's dependency closure. This lexical proof never substitutes for the
  independent semantic support check.
- `ClaimDTO.claim_id` is retained as the statement ID. `observed_fact` and
  `interpretation` map exactly to `EventStatementKind`; `text` is unchanged;
  dependency claim IDs map to dependency statement IDs. Only a claim's source
  ID with a readable registry body maps to `EventStatement.source_ids`. An
  unavailable citation remains in the DTO/validation sidecar, not as a dangling
  EI reference; its statement is not treated as source-supported. Observed facts
  with dependencies are invalid under existing EI rules.
- Only source IDs with registry entries become `EventSourceReference` values;
  include exactly the referenced, body-backed IDs and copy their Host metadata
  exactly. A DTO citation without a readable body is not source evidence.
  Preserve such DTO content in the envelope/validation sidecar, not as a
  fabricated source reference. Source publication time comes from the registry;
  conflicting supplied metadata is a semantic error.
- Hypothesis IDs, impact path, distribution hypothesis, closed distribution
  mode, supporting IDs, contradicting IDs, contradiction review, uncertainties,
  and falsification conditions map without paraphrase or ID rewriting.
  Supporting and contradicting sets remain distinct and disjoint. The builder
  does not reclassify facts as interpretations or drop counterevidence.
- A non-null `underlying_symbol` is bound only by an exact context entry to its
  exact verified `UnderlyingKey`. An absent/unverified binding maps to `None`
  and remains an EI-incomplete hypothesis; it never selects a similar key.
- `expected_window` maps only from the DTO's explicit, semantically validated
  impact-window object. A `reassessment` maps to the existing atomic
  `HypothesisReassessment` only with valid basis statement IDs and matching
  provenance. For a source-backed milestone, the exact ISO reassessment date
  must appear in one directly sourced observed-fact statement in the
  hypothesis's supporting closure, as required by the EI assessor; a separate
  `ClaimDTO.event_date` is insufficient. Caller-policy basis additionally
  requires matching explicit caller authorization and the existing EI closure
  rule: one sourced observed fact and one relevant interpretation in the basis
  closure, with the interpretation retained in supporting closure. Invalid
  asserted temporal fields exclude that hypothesis; the original fields and
  failure reasons remain in the DTO/diagnostic sidecar. No default horizon or
  synthesized temporal value is allowed.
- Submission event ID, producer identity, observation time, and
  `event_date_range` come only from `HostBuildContext`. Claim `event_date` is an
  event-date assertion, not an impact-window boundary; `published_at` is source
  chronology, not event time. Neither may supply
  `expected_window.end_date`. Context event range must have its own evidence
  and methodology; absent evidence stays absent.
- `event_description` copies only the unchanged text of the context-bound,
  surviving source-backed observed-fact statement. Without that binding it is
  `None`: EI may lawfully assess the partial submission as INCOMPLETE with
  `missing_event_description`. Neither model prose nor raw user wording is
  silently promoted to a verified description.

## Quote spans and semantic boundary

`FieldBindingDTO.field_path` uses only the following positional paths into the
exact immutable envelope. `{i}` and `{j}` are in-bounds decimal array indices
without signs or leading zeroes (except `0`). No aliases, wildcards, escaping,
or ID-based lookup are permitted:

| `semantic_role` | Permitted paths |
| --- | --- |
| `hypothesis` | `/hypotheses/{i}/impact_path`, `/hypotheses/{i}/distribution_mode`, `/hypotheses/{i}/distribution_hypothesis` |
| `date` | `/claims/{i}/event_date`, `/hypotheses/{i}/expected_window/start_date`, `/hypotheses/{i}/expected_window/end_date`, `/hypotheses/{i}/reassessment/reassessment_by` |
| `entity` | `/claims/{i}/entity_refs/{j}`, `/hypotheses/{i}/underlying_symbol` |

The terminal field must exist and be non-null; the entity-ref index must
resolve to an existing nonempty item. Unlisted paths fail structural
validation. Multiple bindings for one path are retained, but every supplied
binding for a projected field must pass lexical and semantic checks; an
unresolved or contradictory binding is not silently ignored. For each non-null
field above, at least one verified binding is required before projection.
This does not establish an impact end or listed security identity by itself:
the separate temporal and underlying provenance rules still apply.

For every `FieldBindingDTO`, `start` and `end` are zero-based Unicode codepoint
indices into the exact registered body, with a nonempty half-open span:
`0 <= start < end <= len(body)` and `body[start:end] == quote`. They are not
UTF-8 byte offsets, UTF-16 units, normalized-text offsets, or inclusive ends.
The field path must identify a permitted hypothesis/date/entity target, and
source ID must resolve to that exact body. These checks establish lexical
location only. A matching quote, model `supported` status, or entity/date
string does not establish that the source entails the target field.

The independent semantic validator, not JSON parsing or the builder, must
evaluate attribution, fact-versus-interpretation, support and contradiction,
date role, entity identity, and coverage against readable source content. Its
receipt is retained separately; it cannot mint EI acceptance. If semantic
validation rejects one claim or hypothesis, retain its exact diagnostic while
projecting only unrelated verified hypotheses as specified above. If it
passes with unresolved subquestions or incomplete optional EI fields, preserve
those gaps and let the existing assessor return its exact result. At handoff,
construct the existing `SourceSubmissionBatch` with the **same** `raw_input`
object and call `validate_source_batch`; persist the same `run_id` and
`canonical_input_hash` alongside envelope, receipt, coverage, and typed
submission. Call
`assess_event_intelligence_submission` only after constructing a nonempty,
valid submission; its status and issue codes are never builder outputs.

The Host-produced semantic-validation receipt has this closed v0.1 shape;
model DTO status labels are never copied into it:

```text
SemanticValidationReceipt {
  schema_version: "semantic-validation-v0.1",
  run_id: exact Host run ID,
  canonical_input_hash: exact run_start input SHA-256,
  envelope_hash: SHA-256 of canonical ModelOutputEnvelope JSON,
  source_body_hashes: sorted tuple of (source_id, SHA-256 body hash),
  validator_id: nonempty Host validator identifier,
  validator_version: nonempty version,
  verified_claim_ids: tuple of exact ClaimDTO IDs,
  rejected_claims: tuple of (claim_id, reason),
  verified_hypothesis_ids: tuple of exact HypothesisDTO IDs,
  rejected_hypotheses: tuple of (hypothesis_id, reason),
  verified_binding_indices: tuple of zero-based FieldBindingDTO indices,
  rejected_bindings: tuple of (zero-based binding index, reason),
  coverage_outcomes: tuple of (
    zero-based CoverageDTO index,
    exact subquestion_id,
    "supported" | "unresolved" | "contradicted",
    nonempty validator rationale
  )
}
```

Each claim, hypothesis, and binding index appears exactly once in its verified
or rejected partition. Every CoverageDTO entry has exactly one outcome in the
receipt, and its index/ID must agree with the envelope and original request.
The validator outcome, not the model-authored `CoverageDTO.status`, is used in
Host coverage display; both remain in the sidecar when they disagree. IDs and
indices must resolve to this envelope;
duplicates, overlaps, missing/unknown entries, empty reasons, or identity/hash
mismatch reject the receipt. The Host validates this shape and provenance
before the builder consumes it. Partitioning alone is not proof of truth: the
separate semantic validator must examine readable body content, attribution,
temporal roles, entity identity, interpretation and counterevidence. A verified
hypothesis still projects only when its claim dependency closure and all
applicable field bindings survive.

## Remaining runtime blocker before a live Grounder claim

No production semantic validator currently establishes claim truth,
entailment, or adequate counterevidence review. Passing structural checks or
implementing this builder alone cannot be reported as a live Grounder.
Claim `event_date`/`entity_refs`, field spans, and request coverage remain
identity-bound sidecars, never fabricated EI fields. The builder contract can
be frozen separately from implementing and validating that runtime semantic
gate; no Host/Core success claim follows from a contract freeze.

This blocker is limited to this translation boundary; it does not authorize
new EI/Core frameworks, production changes, tests, live API calls, or broader
Host implementation.
