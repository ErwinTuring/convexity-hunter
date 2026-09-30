# Host Grounder Quote Localization Contract v0.1

Status: **FROZEN — SUBSEQUENT_BUILD_READY** after independent core PASS and
the two requested text clarifications. Runtime implementation is absent; this
freeze authorizes the subsequent build, not live execution or product success.

## Versioned DTO boundary

`grounder-output-v0.2` is the closed producer wire DTO with exactly one change
from v0.1: `field_bindings[]` omits `start` and `end`. Its wire
`schema_version` is exactly `grounder-output-v0.2`. Claim quotes remain
quote-only. Host localization adds derived spans and sets the internal
`schema_version` to exactly `grounder-output-v0.1`; the existing strict v0.1
parser revalidates the complete internal envelope before it is frozen and
hashed. No other internal shape or gate changes.

`semantic-verdict-v0.2` is the closed verifier wire DTO with exactly one change
from v0.1: `evidence_refs[]` omits `start` and `end`. Its wire `schema_version`
is exactly `semantic-verdict-v0.2`. Host independently derives verifier-ref
spans, sets internal `schema_version` to exactly `semantic-verdict-v0.1`, and
applies the existing strict v0.1 reference validation. No other keys, limits,
identities, outcomes, rationales, or evidence requirements change.

Use producer prompt version `host-grounder-discovery-prompt-v0.2`, verifier
wire version `semantic-verdict-v0.2`, and validator/prompt version
`host-grounder-semantic-verifier-prompt-v0.3`. Both wire DTOs remain closed to
extra keys. Legacy v0.1 wire APIs retain their exact behavior and fail closed;
only explicit v0.2 wire dispatch uses this path.

## Host localization and validation order

1. Retain the exact producer assistant-content UTF-8 bytes and hash them before
   parsing. Enforce the existing raw byte cap. Strictly parse the v0.2 wire
   DTO with existing string/array, run/input identity, and coverage checks.
2. For every producer binding, require the registered source ID and exact
   registered body/hash. Locate its unchanged quote literally in that body;
   accept only one occurrence, counting overlaps, and derive its zero-based
   Unicode-codepoint half-open span. Do not normalize, fuzzy-match, infer, or
   rewrite quotes. The model supplies and selects no offset.
3. Construct the internal v0.1 envelope with Host-derived spans; strictly
   revalidate it using the existing v0.1 parser and gates. Freeze the envelope,
   enforce the existing normalized-envelope byte cap, and hash its canonical
   bytes. Send that exact immutable envelope and hash to the verifier.
4. Parse the quote-only verifier v0.2 DTO. Independently validate each
   registered source ID and exact body hash, uniquely locate each unchanged
   quote in the exact body, derive its span, and strictly validate the
   internal v0.1 refs. A supported binding still requires exact source, quote,
   and span agreement between the verifier ref and producer binding.

Missing or ambiguous quotes (including overlaps), unknown sources, body-hash
mismatches, invalid identities, or binding disagreement fail closed. A unique
quote proves location, not entailment. Outcomes, rationales, coverage,
support/closure, counterevidence, dependencies, and EI decisions are unchanged.
All existing request/token/call, raw and normalized byte, string, array,
source, run/input identity, support/closure, counterevidence, and EI gates and
limits remain unchanged; enforce the existing raw and normalized byte caps
independently.

## Closed same-run audit sidecar

The immutable sidecar has exactly these keys, with no additions:

`schema_version`, `run_id`, `canonical_input_hash`, `producer_wire_version`,
`producer_prompt_version`, `producer_content_sha256`,
`normalized_envelope_sha256`, `source_body_hashes`, `verifier_wire_version`,
`validator_version`, `localizer_version`.

Exact version values are:

- `schema_version`: `host-grounder-quote-localization-audit-v0.1`
- `producer_wire_version`: `grounder-output-v0.2`
- `producer_prompt_version`: `host-grounder-discovery-prompt-v0.2`
- `verifier_wire_version`: `semantic-verdict-v0.2`
- `validator_version`: `host-grounder-semantic-verifier-prompt-v0.3`
- `localizer_version`: `host-grounder-quote-localizer-v0.1`

`producer_content_sha256` hashes the exact producer assistant-content UTF-8
bytes. `normalized_envelope_sha256` hashes the frozen internal envelope bytes
sent to the verifier and equals the existing receipt's `envelope_hash`.
`source_body_hashes` is the complete source registry as a list of exact
`{source_id, sha256}` objects, sorted by `source_id`. Serialize the sidecar as
canonical UTF-8 JSON with `ensure_ascii=False`, `sort_keys=True`, compact
separators `(",", ":")`, and `allow_nan=False`. Put the sidecar SHA-256 in the
same-run external audit record; do not add a self-digest key. Retain exact raw
producer bytes or an immutable content-addressed reference under authorized
retention. A digest alone is not replay data; raw bytes do not go in logs or
Git.

Provenance stays outside the closed receipt and EI/Core. Receipt and Builder
v0.2 shapes and behavior remain unchanged; Semantic Validation v0.3 specifies
this versioned path. Existing v0.1/v0.2 APIs remain exact and fail-closed.

## Minimal adversarial matrix

| Case | Required result |
| --- | --- |
| Astral Unicode before quote; exact CRLF body | Derive codepoint span; exact slice matches; do not normalize line endings. |
| Repeated or overlapping quote | Reject as ambiguous; never select one. |
| Missing quote, unknown source, or body-hash mismatch | Fail closed. |
| Producer binding and verifier ref | Localize independently; supported binding requires exact source/quote/span agreement. |
| Raw/normalized byte cap or run/input/hash mismatch | Reject; sidecar and verifier input remain bound to this run. |
| Unique quote with unresolved/contradicted verdict | Preserve verdict; lexical location does not upgrade support. |

This contract, including the ownership addendum below, is frozen for the
subsequent build under the scope above.

## Ownership addendum — single-run audit holder

The explicit quote-localization route requires a caller-created,
repr-hidden, write-once in-memory holder bound to the exact `run_id` and
`canonical_input_hash`. Reject an unbound or reused holder before model calls.
Immediately after discovery, retain the exact producer UTF-8 bytes and SHA-256
before parsing. After strict normalization succeeds, finalize and retain the
closed sidecar and its external digest before the semantic call. Producer
parse/gate failure therefore leaves raw bytes/hash retained without a
finalized sidecar; any later semantic or Builder failure leaves the finalized
audit accessible through the caller's holder. Exceptions and logs never carry
the raw content, normalized bytes, or sidecar JSON. This ownership guarantee
adds no persistence service and does not change legacy APIs.
