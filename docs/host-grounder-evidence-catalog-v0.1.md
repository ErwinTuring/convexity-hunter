# Host Grounder Evidence Catalog Contract v0.1

Status: **FROZEN — SUBSEQUENT_BUILD_READY** after independent targeted
contract review and Main freeze. Implementation was absent at that freeze;
the explicit route is now implemented with synthetic/regression validation,
but has not completed live validation. See the current checkpoint for runtime
evidence. This contract defines the explicit catalog route;
existing v0.1/v0.2 wire routes and APIs keep their exact behavior and fail
closed, with no legacy reinterpretation.

## Versioned wire boundary

- Producer `grounder-output-v0.3` is closed. In each claim, replace
  `source_id`, `locator`, and `quote` with exactly one `evidence_id`. In each
  field binding, starting from v0.2 (which has no offsets), replace
  `source_id` and `quote` with exactly one `evidence_id`. All other keys,
  shapes, limits, identities, coverage, and outcomes are unchanged.
- Verifier `semantic-verdict-v0.3` is closed. Each `evidence_refs[]` item is
  exactly `{ "evidence_id": <string> }`; the model supplies no source ID,
  hash, text, or offset. All other keys, shapes, limits, identities,
  rationales, and outcomes are unchanged.
- Use producer prompt `host-grounder-discovery-prompt-v0.4` and verifier
  prompt/validator `host-grounder-semantic-verifier-prompt-v0.5`. Dispatch
  these versions explicitly. Internal normalized producer and verifier DTOs
  remain `grounder-output-v0.1` and `semantic-verdict-v0.1`, respectively.

## Deterministic host catalog

Before either model call, copy and freeze the complete registered source
registry (including each source's final locator) and exact body strings. Hash
each body's strict UTF-8 bytes with SHA-256. `source_body_hashes` is the
complete registry as `{ "source_id": ..., "sha256": ... }` objects sorted
by `source_id`; do not omit sources without eligible paragraphs.

Split each body into lines with endings, recognizing only LF and CRLF as line
delimiters (the `splitlines(keepends=True)` behavior for these delimiters).
Bare CR and all other separators are literal characters. A line is blank iff,
after removing its LF and only the CR immediately preceding that LF, its
content is empty or consists solely of ASCII space and tab. A paragraph is a
maximal consecutive run of nonblank lines. Its half-open offsets are Python
Unicode-codepoint indices into the unchanged body, from the first character
of its first line through the end of its last nonblank line, including that
line's ending. Its quote is exactly `body[start:end]`; perform no trimming,
normalization, newline conversion, or repair.

For each candidate paragraph, count exact quote occurrences in its own body,
including overlapping matches (advance the search start by one codepoint).
Count candidates with occurrence count other than one in that source's
`nonunique_paragraphs`. Independently count candidates whose strict UTF-8
quote length exceeds the existing `max_string_bytes` in
`overlong_paragraphs`; these reason counts may overlap. A candidate is
eligible only when unique and within that byte limit. Emit every eligible
paragraph, sorted by `(source_id, start)`; do not rank, select, or truncate.

The exact catalog object has only these keys:

```json
{
  "schema_version": "host-grounder-evidence-catalog-v0.1",
  "run_id": "...",
  "canonical_input_hash": "...",
  "generator_version": "host-evidence-paragraph-generator-v0.1",
  "source_body_hashes": [],
  "entries": [],
  "exclusions": []
}
```

Each entry has exactly `{evidence_id, source_id, body_sha256, start, end,
quote}`. Each exclusion has exactly `{source_id, nonunique_paragraphs,
overlong_paragraphs}`; emit one sorted exclusion object per registered source,
including zero counts. `body_sha256` is that source's exact body hash. Assign
IDs only after sorting: let `seed` be the full lowercase SHA-256 hex digest of
canonical UTF-8 JSON for exactly
`{run_id, canonical_input_hash, source_body_hashes, generator_version}`;
then set `evidence_id` to `evidence-` + `seed` + `-` + `str(global_ordinal)`,
with ordinal starting at zero and increasing across the sorted entries.

Canonical JSON everywhere in this contract is UTF-8 with
`ensure_ascii=False`, `sort_keys=True`, separators `(",", ":")`, and
`allow_nan=False`. After IDs are assigned, serialize the complete catalog
canonically and compute `catalog_sha256` over those bytes; the digest is not a
catalog field and is not included in the seed.

Callers must supply required positive exact-`int` bounds
`max_catalog_entries`, `max_catalog_bytes`, and `max_catalog_paragraphs`.
The paragraph bound counts all candidate paragraph spans across the complete
registry before eligibility filtering. Entry and byte bounds apply to the
complete eligible entries and final canonical catalog bytes, respectively.
Reject nonpositive, non-exact-int, or exceeded bounds; never return a partial
catalog. Existing source, request/model, string, array, and input-byte caps
also apply. Zero eligible entries is a pre-call failure. Send the full frozen
source-body context and complete catalog to both discovery and verification,
within existing input caps; no body summaries, evidence hiding, or truncation.

## Resolution and unchanged semantics

Accept an `evidence_id` only by exact lookup in this run's immutable catalog.
Reject duplicate catalog IDs, unknown/foreign-run IDs, changed source/body
hashes, and any catalog/run/input identity mismatch. Duplicate evidence refs
within one verifier record are invalid. Reuse of an ID across claims,
bindings, or separate records is allowed.

Host expands each ID from the frozen entry and source registry: source ID,
body hash, exact quote and codepoint span come from the entry; a claim's
internal `locator` is the registered `final_locator`. Reconstruct the
unchanged internal v0.1 DTOs (only fields in their existing shapes), then
apply their existing strict validators. Producer bindings and verifier refs
must independently resolve in the same catalog; a supported binding requires
exact evidence-ID, source, body-hash, quote, and span agreement. Preserve all
existing run/input identity, coverage, closure, date/identity, support,
counterevidence, dependency, fallible-entailment, and contradicted/unresolved
rules. Catalog membership and lexical location alone never establish
entailment or upgrade an outcome. The existing receipt builder v0.2 and
receipt-validation API remain unchanged.

## Same-run audit and retention

The exact closed sidecar keys are `schema_version`, `run_id`,
`canonical_input_hash`, `producer_wire_version`, `producer_prompt_version`,
`producer_content_sha256`, `normalized_envelope_sha256`, `source_body_hashes`,
`verifier_wire_version`, `validator_version`, `localizer_version`,
`catalog_schema_version`, `catalog_generator_version`, and `catalog_sha256`.
Set `schema_version` to `host-grounder-quote-localization-audit-v0.3`;
set producer/verifier wire and prompt/validator values to the versions in this
contract; and set `catalog_schema_version` to
`host-grounder-evidence-catalog-v0.1`, `catalog_generator_version` to
`host-evidence-paragraph-generator-v0.1`, `catalog_sha256` to the digest
above, and `localizer_version` to
`host-evidence-catalog-resolver-v0.1`.
Only this v0.3 sidecar uses the new resolver identity; legacy v0.1/v0.2 audit
records remain unchanged. The producer digest covers exact assistant-content
UTF-8 bytes; the normalized digest covers the frozen internal envelope sent
to verification and equals receipt `envelope_hash`; `source_body_hashes` is
the complete sorted registry. Serialize with the canonical JSON encoding
above; the sidecar digest stays in the external same-run audit record, never
as a self-field.

Use a caller-created, repr-hidden, write-once holder bound to exact `run_id`
and `canonical_input_hash`; reject an unbound or reused holder before calls.
Retain immutable copies of catalog bytes/digest before discovery. Immediately
after discovery, retain exact producer UTF-8 bytes/digest before parsing.
After strict normalization, retain normalized bytes/hash and finalized
sidecar before the semantic call. Keep catalog, raw producer, normalized
envelope, and sidecar available in that holder across later failures. Do not
log or repr raw bytes, catalog/envelope bytes, or sidecar JSON; do not put
those runtime payloads in Git. No mutable catalog changes are permitted after
the pre-call snapshot.

## Minimum adversarial cases

| Case | Required behavior |
| --- | --- |
| Astral Unicode; LF, CRLF, and bare CR | Exact original body slice and codepoint offsets; CRLF retained, bare CR literal. |
| Repeated/overlapping paragraph; overlong paragraph | Exclude and count by source; never choose an occurrence or truncate. |
| No eligible entries; any new catalog bound exceeded | Fail before model calls; never expose a partial catalog. |
| Unknown/foreign ID, duplicate catalog ID, changed body/hash, run/input mismatch | Fail closed against the frozen same-run registry/catalog. |
| Duplicate refs in one verifier record; ID reused across records | Reject the former; allow the latter. |
| Supported, unresolved, or contradicted semantic result | Preserve existing verdict rules; lexical membership alone does not decide support. |
| Full bodies/catalog exceed existing input caps | Fail closed before the affected call; do not summarize or hide evidence. |
