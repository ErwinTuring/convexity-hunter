# Host verifier bound-object wire v0.1

Status: FROZEN / IMPLEMENTED / REVIEW PASS. Implementation follows the separately
committed contract freeze, at which production was absent. Full regression
passes 2,051 tests; focused adversarial tests, public API compatibility,
compileall and independent implementation/test review pass. Deployment and
real integration are still pending. User approval covers this bounded successor.

## Purpose and boundary

The user approved a bounded verifier-protocol preflight after real run
`7cc1b60e` failed `PRODUCER_BINDING_ALIGNMENT`. Its precise failed subcheck
and original response remain unknown. This design removes redundant binding
correspondence generation; it does not claim to reconstruct or fix that run.

Host owns which exact binding is assessed. The independent model owns its
supported/contradicted/unresolved judgment and rationale. Identity membership
is never evidence of support. No EI/Core rule, source permission, hypothesis,
producer wire/prompt, budget, model, retry or screening policy changes.

## Explicit successor only

- New verifier wire: `semantic-verdict-v0.4`.
- New verifier prompt/validator: `host-grounder-semantic-verifier-prompt-v0.9`.
- New private runtime route: `_run_host_grounder_same_run_evidence_catalog_v0_10`.
- Producer remains `grounder-output-v0.3` / discovery prompt v0.9; internal
  verdict remains `semantic-verdict-v0.1`, receipt `semantic-validation-v0.2`.
- After BUILD/review, the existing default Event factory selects the new route;
  World reuses that factory. Direct and all explicitly older routes keep their
  exact behavior. No public callable/export/signature is added or changed.
- Never accept v0.4 as legacy v0.3, repair a legacy response, infer a version,
  fall back to an older parser, or rerun a model after a wire rejection.

## Immutable input and closed output

After the final producer attempt has passed all existing checks, generate
`host_binding_objects` in normalized producer binding order. Each item has
exactly `{binding_id, index, evidence_id}`. For index `i`, the ID is exactly
`binding-<full lowercase normalized-envelope SHA-256>-<decimal i>` (zero has
no padding). Repeated evidence IDs are legal; binding IDs remain distinct.
The Host must validate correspondence to the accepted normalized envelope and
the same run's frozen catalog before using the map. Do not use a first-attempt
hash/map after an approved producer format repair.

Keep the complete existing envelope, registered bodies, catalog, run identity,
ordered subquestions and source hashes in the model input. The map is lexical
correspondence only, not a verdict, authority or instruction from source text.
All existing byte/string/array/request limits apply before dispatch; never
truncate evidence, omit bindings or increase a budget to make it fit.

All v0.3 top-level keys and other sections remain unchanged apart from the
explicit schema version. Only each `field_bindings[]` record changes to:

```json
{
  "binding_id": "HOST_SUPPLIED_BINDING_ID",
  "outcome": "supported",
  "rationale": "Independent judgment of the specified original binding.",
  "evidence_refs": []
}
```

This is a shape example, not a default outcome or evidence. The record has
exactly these four keys; `outcome` retains the existing closed enum, rationale
and ref limits. The sole nonempty-reference exception is a supported binding:
its refs may be `[]` because its primary citation is implicit. Supported
claims/hypotheses/coverage and all contradicted records still require explicit
nonempty references; unresolved retains its existing empty-ref permission.
Record count and ordered ID sequence must equal the complete
Host map exactly, including `[]` for zero bindings. Missing, duplicate, foreign,
malformed, mismatched or reordered objects fail closed as a whole. No numeric
coercion, sorting, ID correction, partial verdict or default outcome is allowed.
Claims, hypotheses, coverage, global hashes and all their references retain
their existing independent-verification requirements.

## Judgment and reference normalization

`supported` explicitly attests that this object's original bound paragraph,
read in its full source/dependency context, supports the asserted field in its
declared role. It does not attest merely that some other paragraph supports a
similar value or that the hypothesis is plausible. Existing v0.8 fact versus
interpretation, conditional-transmission and contrary-evidence rules remain.

On that explicit supported judgment only, Host supplies the object's already
fixed primary catalog reference when absent from `evidence_refs`. If present
exactly once, keep it and its position unchanged. Otherwise prepend it, while
preserving every model-selected reference and their relative order. Validate
all model refs first: duplicates, unknown IDs and malformed refs are errors,
not candidates to discard or replace. The resulting legacy record's `index`
comes only from the exact Host object. Existing catalog expansion, exact
source/hash/quote/span checks and receipt construction still run unchanged.

For `contradicted` and `unresolved`, never inject or replace any reference.
Explicit contradictory evidence remains mandatory under the existing rules;
unresolved may have none. No Host status/rationale is synthesized. This is a
new wire's declared implicit citation, not a repair or reinterpretation of a
malformed legacy supported verdict. If original-paragraph support is absent,
the correct model judgment remains unresolved/contradicted; Host identity
cannot cure it. Fallible model judgment remains a limitation, not factual proof.

For each valid new verdict, its explicit-reference legacy counterpart must
normalize to the same internal judgment, evidence and receipt checks. Old
routes retain literal/golden behavior. A changed validator-version provenance
is expected and must not be hidden as identical old receipt bytes.

## Audit and integration

Retain existing audit keys and v0.3/v0.4 structural schemas (including the
existing producer-repair distinction). Record actual verifier wire v0.4 only
with verifier prompt v0.9 and producer prompt v0.9 on the new route; old pairs
remain exact. No new retention, raw payload, database schema or log is added.
Counterreferences are preserved through normalization and receipt validation;
this does not claim new durable retention of original verifier references.

Preserve the same approved producer format/append-only binding repair under
the new version pair, with identical limits and constraints; no new retry is
introduced. Existing closed failure diagnostics may be reused on the new
route with explicit version-pair guards. Historical records are not upgraded.

## Acceptance checks and next work

Test all three outcomes, repeated/empty primary IDs, immutable map derivation,
post-producer-repair identity, full count/order/ID rejection, foreign-run and
envelope/source mutation, invalid extra refs, explicit counterevidence, and
supported/unresolved non-promotion. Compare valid normalized legacy counterparts
and preserve literal old prompt/parser/audit behavior and public API counts.
Verify selected wire/prompt/audit pairing, bounded overflow before dispatch,
default Event and World sharing the route, and an offline accepted EI path
without injected verdicts. Run focused/relevant regression, compile/diff/docs
checks and independent implementation review before commit/deployment.

No live call during BUILD. Any subsequent bounded normal integration run uses
fresh current evidence and a new one-shot guard, never an old response or
spent run. Success is lawful execution or precise refusal, not forced EI
acceptance or investment value. Stop on an unresolved authority-equivalence
counterexample rather than implementing around it.
