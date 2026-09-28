# Host Semantic Validation Contract v0.1

Status: **FROZEN / SUBSEQUENT_BUILD_READY** after independent Tier-A review and
targeted re-review. It defines a conservative, bounded Host evidence-assessment
boundary; it does not prove semantic truth, authorize live calls, or claim a
working validator. Live integration requires a separate real trial.

This contract complements the
[semantic verification design](event-grounder-semantic-verification-design-v0.1.md)
and the frozen [Builder contract](host-grounder-builder-v0.1.md). EI's existing
assessor remains the sole EI acceptance authority. No EI/Core fields, statuses,
issue codes, providers, or downstream acceptance rules are added or changed.

## Authority and bounded procedure

The Host assesses whether exact, retained source bodies support a claim as
represented, with its attribution, polarity, date role, and entity. This is a
fallible semantic judgment, not a deterministic proof that the claim is true
in the world. In particular, `verified_*` in the existing receipt means only
“eligible as evidence-supported under this bounded assessment”; it must not be
presented as factual certainty. A causal or market-impact path remains a
hypothesis, not a source-established outcome.

For each run, bind the original input and ordered subquestions, run/input
identity, configured semantic-model identity/version, and finite source/model
limits before assessment. Missing or exceeded limits stop; no budget is silently
extended. After the producer call returns the untrusted envelope, make one
separate bounded semantic-verifier model call. Give it the exact canonical
envelope, original subquestions, and exact registered body texts plus IDs and
hashes. It has no tools or network access and cannot change budgets. Use the
already configured model/provider only; the verifier does no retrieval.

The verifier returns exactly this closed JSON DTO (no extra keys, prose, or
markdown). Every expected claim, hypothesis, binding index, and request coverage
item appears exactly once. `evidence_refs` may be empty only for `unresolved`;
otherwise at least one exact body reference is required.

```text
SemanticVerdict {
  schema_version: "semantic-verdict-v0.1",
  run_id: nonempty string,
  envelope_hash: lowercase SHA-256,
  source_body_hashes: SourceBodyHashDTO[],
  claims: ClaimVerdictDTO[],
  hypotheses: HypothesisVerdictDTO[],
  field_bindings: BindingVerdictDTO[],
  coverage: CoverageVerdictDTO[]
}
SourceBodyHashDTO = {source_id: nonempty string, sha256: lowercase SHA-256}
ClaimVerdictDTO = {claim_id: exact envelope ID, outcome, rationale, evidence_refs}
HypothesisVerdictDTO = {hypothesis_id: exact envelope ID, outcome, rationale, evidence_refs}
BindingVerdictDTO = {index: exact envelope index, outcome, rationale, evidence_refs}
CoverageVerdictDTO = {index: exact request index, subquestion_id: exact request ID,
                      outcome, rationale, evidence_refs}
outcome = "supported" | "contradicted" | "unresolved"
rationale = nonempty UTF-8 string within configured string limit
evidence_refs = EvidenceRefDTO[]
EvidenceRefDTO = {source_id: exact registered ID, body_sha256: lowercase SHA-256,
                  start: nonnegative integer, end: integer > start, quote: nonempty string}
```

All objects above are closed to additional keys. `source_body_hashes` is sorted
by unique source ID and equals the complete run registry. Supported or
contradicted verdicts require at least one evidence ref; unresolved may use an
empty list only when the rationale identifies missing/unreadable evidence.
For a supported claim, one ref must match its DTO `source_id` and `quote`; for
a supported binding, one ref must exactly match its DTO source, quote, and
span. Hypothesis/coverage references must still be exact registered body
references; their semantic relation to the item is the verifier's fallible
judgment, while IDs and dependency closure are Host-checked.

Host strictly parses within configured byte/string/array limits, rejecting
duplicate JSON keys, unknown/missing fields, duplicate/foreign IDs, and missing
outcomes. It binds run/envelope/body hashes to this run; checks each reference's
source/hash and Unicode-codepoint half-open span (`body[start:end] == quote`);
matches IDs and coverage order; and enforces verified dependency closure
before making the receipt. Refs are locators, not proof. The verifier assesses
claims in context; neither source self-labels nor producer-model statuses are
sole authority.

Assess only readable Host-registered bodies acquired within the authorized
source budget. Retain each exact UTF-8 body (or immutable body record), hash,
source ID, final locator, and retrieval metadata. URLs, snippets, titles,
domains, and publication metadata alone are not evidence. Parse the exact model
envelope under the closed schema; model labels, locators, quotes, spans, dates,
entity strings, and hypotheses are candidate assertions only. Recheck source
ID/hash/quote/span against the exact body; lexical location is not entailment.

For each claim, assess the source's actual wording, speaker/attribution,
negation, qualification, and scope. Preserve allegations as attributed claims,
not as established underlying facts. Keep publication/update dates, event dates,
impact windows, and reassessment dates distinct: event dates need direct
role-specific support; no URL/date substitution or inferred impact end is
allowed. Reassessment follows only existing source-milestone or explicitly
authorized caller-policy rules. Resolve securities only through exact
Host-bound listing identity, never ticker/name similarity; collisions remain
unresolved.

Review counterevidence only in the retained bodies and separately authorized
bounded source work. Record inspected scope and material conflicts/gaps in
Host-owned coverage rationale or rejection reason. No source-count vote,
automatic “newer/official wins,” or global-absence claim: “not found” means
only not found in the recorded bounded set.

Parsing, limits, hashes, lexical identity, provenance, partitions, dependency
closure, projection, and EI assessment are deterministic. Entailment,
attribution fidelity, date meaning, entity relationships, and counterevidence
weight remain fallible semantic judgments; the Host cannot turn them into proof.

## Outcomes and downstream boundary

Only verifier `supported` plus all deterministic gates can enter a Host
verified partition. `contradicted` and `unresolved` both fail closed: reject
that item with its rationale; map either coverage verdict to Host `unresolved`
(the Host does not prove refutation). Missing, empty, or unreadable evidence is
unresolved. A supported coverage verdict is Host `supported` only when its refs
and all associated claim checks pass.
Project only complete verified dependency closures, locally: preserve unrelated
valid hypotheses and rejected/unresolved sidecars. With no readable body or
projectable hypothesis, stop before EI/Core and emit no empty submission. A
genuine partial submission may reach the existing EI assessor; only it decides
`ACCEPTED`/`INCOMPLETE` and issue codes. Neither proves world truth, causation,
investment merit, or Core readiness.

## Receipt provenance and runtime authority

Keep the Builder's closed receipt payload: run ID, canonical input/envelope
hashes, sorted exact body hashes, validator ID/version, claim/hypothesis/binding
partitions, and one Host outcome per original subquestion. Bind validator
identity/version to the same run's semantic-model configuration. Retain the
envelope and exact bodies (or immutable content-addressed references) for audit;
serialized receipts are not runtime credentials.

API compatibility: `build_host_grounder(envelope, receipt: Mapping, ...)`
remains a low-level structural projection API for tests and controlled calls.
It validates supplied receipt structure/identity; it does not authenticate the
issuer, and direct callers can construct mappings that pass those checks. The
product runtime entry point must expose no receipt parameter: its same-run
orchestrator obtains the producer envelope, makes the separate verifier call,
strictly checks the verdict, constructs the Host receipt internally, then calls
the Builder. This is an application call-path rule, not a magic Python
capability or cryptographic security guarantee. Persisted receipts are audit
records, not inputs that bypass a fresh run's verifier.

**Current implementation gap:** `host_grounder_receipt.py` checks receipt
shape, hashes, partitions, and lexical locations, not semantic support or
issuer identity. The low-level `Mapping` API remains intentionally structural;
this contract does not claim it authenticates receipts. The product orchestration
and separate verifier protocol are not implemented or live-validated by this
documentation freeze.

## Human confirmation and adversarial acceptance matrix

There is no mandatory human checkpoint. Ambiguous listing identity, material
source conflict, or uncertain interpretation remains unresolved and is not
projected. A human correction requires an explicit fresh submission/run with
its own provenance; it never edits a verdict/receipt or automatically promotes
the prior unresolved assertion.

| Case | Required result |
| --- | --- |
| Quote is negated or is attributed speech/allegation | Preserve polarity and speaker; support only the attributed statement actually in the body, not the alleged underlying fact. |
| Publication/update date is offered as event date; impact end is conflated with reassessment | Keep roles separate; unsupported dates/windows stay absent or unresolved. |
| Ticker collides with another issuer/security or affiliate | Require exact Host-bound listing identity; otherwise leave underlying unresolved. |
| Later official body conflicts with an earlier body | Assess both within the bounded set; no recency, official-domain, or source-count shortcut. Unresolved absent an evidenced resolution. |
| Body is empty, unreadable, or unavailable | It supports nothing. If no readable evidence/surviving hypothesis remains, stop before EI/Core with no empty submission. |
| Source body contains prompt/tool instructions | Treat as untrusted text; it cannot change policy, budgets, credentials, tools, or instructions. |
| Model labels its own claim/field/hypothesis “supported” | Ignore the label as authority; only the Host assessment can populate verified partitions. |
| Caller supplies a well-formed, correctly hashed receipt mapping | Product runtime exposes no receipt parameter; the low-level Builder may accept it for controlled structural use but does not authenticate its issuer. |
| One hypothesis is unresolved while another has an independent verified closure | Exclude the affected hypothesis/closure; preserve the unrelated valid hypothesis and its provenance. |
| No counterevidence appears in the bounded retained bodies | Report only that bounded observation and its scope; never assert global absence. |

This matrix is not evidence the current runtime passes. Implementation/tests
are later work. No live calls occur under this freeze; integration remains
unclaimed until the receipt boundary is implemented and a separately authorized
real trial exercises the bounded source/model path, reporting EI separately.
