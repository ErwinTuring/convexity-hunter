# Host Event Source Facts v0.5

Status: FROZEN / IMPLEMENTED / INDEPENDENT CONTRACT AND IMPLEMENTATION REVIEW PASS.

The contract was committed before BUILD. The default normal route and closed
v0.3 audit are implemented; old/custom routes and public interfaces remain
compatible. Final full regression passed 2,022 tests; Event 58, Store 54 and
HostServer 53 focused checks passed. Review's pre-existing-binding date
mutation was corrected and passed targeted re-review. This is implementation
validation, not evidence of a new live EI/Core acceptance.

## Scope and compatibility

This successor changes only the default normal Event preparer
(`host_context_preparer is None`): its event-fact anchor selection and closed
stage-outcome audit record. Public/custom `host_context_preparer` callers keep
the existing single-question path and old outcome versions/behavior, including
their existing supplied-description handling; they do not acquire a mandatory
v0.3 anchor gate. The v0.1-v0.4 helpers and historical archives retain their
existing behavior. The public Event API, producer/verifier prompt versions,
model DTOs, semantic receipt schema, provider/model budgets, source-admission
rules, EI acceptance, and Core policy are unchanged.

Reuse `host-grounder-run-input-v0.1`, its ordered subquestion list, the existing
producer coverage rows, verifier coverage verdicts, and semantic receipt. The
default normal route predeclares exactly these two ordered questions:

1. `user_event_input`, with its existing text equal to the user's original
   event input, unchanged.
2. `event_fact_anchor_v0_1`, with this fixed text:

   > Does exactly one registered source-backed observed_fact directly state
   > the event described by the user's event input? Assess only event identity
   > and direct relevance. Do not assess economic materiality, market impact,
   > transmission mechanism, underlying or listing identity, event timing, or
   > completeness of the broader research answer. Identify exactly one
   > claim_id only when that fact is uniquely supported and unambiguous;
   > otherwise leave this subquestion unresolved and state the gap.

The stable, versioned subquestion ID identifies this question in coverage and
history. Its exact text is part of the existing canonical run-input bytes and
hash. The fixed ID and text must not be silently repurposed.

## Independent fact-anchor gate

The anchor is selected only from the `event_fact_anchor_v0_1` coverage row; the
research `user_event_input` row is never a fallback. Selection requires all of
the following:

1. The envelope contains exactly one row for the anchor ID, in the
   predeclared order. Its producer status is exactly `supported`, its `gap`
   key is present and `null`, and its `claim_ids` array contains exactly one
   nonempty ID.
2. That ID resolves to exactly one envelope claim that is an eligible
   `observed_fact`, appears in the same-run receipt's verified claim IDs, and
   passes the existing exact registered-source, locator, hash, and unique
   quote checks. No sorting, first-item, date, source, or ID preference is
   permitted.
3. The receipt has exactly one coverage outcome for the matching anchor
   index and ID, with validator status exactly `supported`. The existing
   semantic verifier must validate its evidence references against registered
   source bodies and the verified claim's source. Producer support alone is
   insufficient.
4. Any missing, duplicate, malformed, unresolved, contradicted, conflicting,
   ambiguous, or mismatched anchor row, claim, source, hash, quote, index, or
   receipt outcome yields no selected anchor. In particular, a singleton
   eligible fact does not bypass this identity-and-relevance gate.

The verified fact supplies factual support; the separately supported anchor
coverage supplies relevance to the named event. The broader research coverage
retains its original status and gap. It may be unresolved or contradicted with
a gap while the independent anchor passes; this does not make the broader
research answer complete or supported. A supported anchor row with a non-null
gap is rejected.

The gate may fill only an originally absent `event_description_binding`. If
the original context already has a nonempty description binding, preserve it
exactly and record `selected_claim_id: null`; do not require it to equal or be
re-established by the anchor gate. If the original binding is absent and the
gate passes, bind exactly the gate-selected claim ID. If it is absent and the
gate does not pass, leave it absent. Preserve all other context fields by
identity. Do not infer an anchor from the user input, global fact count,
research coverage, or another claim.

## Date and downstream limits

For the default normal preparer, an absent anchor must remain absent: do not
fall back to the legacy v0.2/v0.3 automatic fact-selection helpers, including
when there is only one eligible fact. After a passing anchor gate only, reuse
the existing v0.4 occurrence-date rules on that exact selected fact. No other
fact may lend it a date. This contract does not create an underlying key,
impact path, distribution mode or hypothesis, expected window, reassessment,
falsification condition, or EI acceptance. All existing semantic, Builder,
EI, listing, and Core gates remain mandatory.

## Closed audit outcome

Only the default normal preparer route with the exact two-question tuple above
emits the new outcome versions. Public/custom preparers continue to emit the
existing outcome versions. The private stage outcome records the fixed anchor
question ID and the claim ID used to fill an originally absent binding, or
`null` otherwise. Version the existing closed outcomes as:

- `host-grounder-stage-outcome-v0.3`
- `host-grounder-submission-stage-outcome-v0.3`

Each v0.3 outcome adds exactly this closed object:

```json
{
  "event_fact_anchor": {
    "subquestion_id": "event_fact_anchor_v0_1",
    "selected_claim_id": null
  }
}
```

`selected_claim_id` is non-null only when the gate fills an originally absent
binding; otherwise it is `null`. At outcome creation, Host must validate the
conditional relation against the original and prepared contexts and the same
validated envelope/receipt: for an original nonempty binding, the prepared
binding is unchanged and audit selection is null; for an original absent
binding with a passing gate, audit ID, gate ID, and prepared binding are equal;
for an original absent binding without a passing gate, audit selection is
null and the prepared binding remains absent. A claim ID may not be asserted
merely from model output. The v0.3 validators preserve the existing base
validation path indicated by archived producer-attempt provenance: without
`producer_attempts`, run the unchanged v0.1 validator; with `producer_attempts`,
run the unchanged v0.2 validator, including its attempt-sequence and
repair-identity checks. Then validate only the new closed anchor object and the
creation-time conditional correspondence. Do not duplicate or weaken either
base validation path. Existing v0.1/v0.2 outcome validators and archives
remain readable and unchanged. No diagnostic framework or free-form reason is
added.

## Required tests

- Default normal factory constructs exactly the two fixed questions in order; the
  original research question bytes remain unchanged; the canonical hash binds
  both questions; producer and verifier coverage IDs/outcomes must match.
- With multiple verified facts, a supported, gap-free anchor row naming one
  exact eligible fact selects it even when `user_event_input` remains
  unresolved/contradicted with an economic-materiality gap. Research coverage
  remains unchanged.
- The anchor does not select when its row is missing, duplicated, unresolved,
  contradicted, supported-with-gap, multi-ID, or mismatched to the receipt; nor
  when the selected claim is unverified, not an observed fact, ambiguous,
  duplicate, or has invalid source/hash/locator/quote evidence.
- A singleton global fact without a passing anchor row remains unselected.
  Permuting claim order or unrelated sources never changes the selected ID.
- With an original nonempty description binding, preserve it exactly, record
  `selected_claim_id: null`, and do not require equality to an anchor claim.
  With an originally absent binding, test both exact fill on a passing gate
  and continued absence/null audit selection when the gate does not pass.
- Date derivation uses only the selected claim and the unchanged v0.4 grammar.
  EI fields and acceptance remain unchanged and are not synthesized.
- v0.3 outcomes record the anchor question and exact selected ID, or `null`,
  and reject any outcome inconsistent with the same envelope/receipt/context;
  they inherit all v0.2 audit checks. The default normal route uses these
  outcomes, while the custom-preparer route remains on its legacy single
  question and outcome versions. Existing v0.1/v0.2 outcomes and historical
  archives still validate.

No live operation, production change, or historical-result rewrite is part of
this contract review.
