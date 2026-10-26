# Host Event Source Facts v0.6 — Unique Event, Single Verified Witness

Status: FROZEN AND APPROVED; IMPLEMENTED; FINAL INDEPENDENT IMPLEMENTATION REVIEW PASS.

This is the successor to `host-event-source-facts-v0.5` for new default normal
Event preparation only. It changes the anchor question's identity criterion.
The v0.1 question and existing v0.1-v0.5 receipts/outcomes remain historical,
readable, and unchanged; no archive migration or relabeling is allowed.

## Versioned question and canonical input

Keep `user_event_input` and its original text unchanged. The second ordered
question uses the new ID `event_fact_anchor_v0_2` and exactly this single-line
text, with no leading/trailing whitespace or newline:

```text
Does the registered source-backed evidence identify exactly one event identity matching the event described by the user's event input? If multiple observed_fact claims directly support that same event identity, identify exactly one claim_id as the single binding witness; that witness does not imply other supporting facts are absent. If directly relevant observed_fact claims that are candidates for identifying the event described by the user's event input support distinct competing event identities, conflict, or leave the matching identity ambiguous, identify no claim_id and state the gap. Assess only event identity and direct relevance. Do not assess economic materiality, market impact, transmission mechanism, underlying or listing identity, event timing, or completeness of the broader research answer.
```

The ordered tuple is `(user_event_input, event_fact_anchor_v0_2)`. Keep the
`host-grounder-run-input-v0.1` schema and canonical JSON encoding unchanged:
the exact new ID and text above are included in its existing UTF-8 canonical
bytes and SHA-256. The v0.1 ID/text and their hashes are never repurposed.

## Single-witness gate

For the default normal route, accept an anchor only when the same-run v0.2
coverage row is uniquely present in the declared order, producer-supported,
gap-free, and names exactly one nonempty `claim_id`; the matching same-run
receipt outcome is validator-supported. That claim must be one independently
verified, registered-source-backed `observed_fact` with direct evidence for
the unique event identity. Preserve the existing source, locator, hash, quote,
index, and receipt checks from v0.5.

Multiple verified facts or sources may support the same unique event. The
coverage/receipt still selects exactly one as the binding witness. Host must
not choose among facts, sort or prefer sources, use first-item fallback, combine
claim IDs, or infer identity from another question. If directly relevant
`observed_fact` claims that are candidates for identifying the event described
by the user's event input support distinct competing event identities, conflict,
or leave the matching identity ambiguous, no anchor is selected. Unrelated or
background facts that mention other events do not by themselves veto the anchor.
Missing/mismatched evidence, unresolved coverage, or multiple nominated IDs also
yield no anchor. The witness does not assert that it is the only supporting fact.
Broader research coverage and its status/gap remain unchanged.

As in v0.5, fill only an originally absent `event_description_binding`, using
the exact selected witness ID; otherwise preserve the original binding. Derive
an absent event date only from that selected witness under the unchanged v0.4
occurrence-date rules. No other fact may supply its date. Listing identity,
time fields, economic hypothesis, semantic verification, Builder, EI, and Core
standards do not change; do not synthesize any of them. No event graph or
identity registry is introduced.

## Outcome and archive compatibility

Only the new default normal route with the exact v0.2 question tuple emits
`host-grounder-stage-outcome-v0.6` or
`host-grounder-submission-stage-outcome-v0.6`. Each retains the existing closed
`event_fact_anchor` shape and records `subquestion_id: "event_fact_anchor_v0_2"`.
Custom-preparer routes retain their existing behavior and outcome versions.
Readers continue validating v0.1-v0.5 records under their original rules;
v0.1 coverage/receipts cannot satisfy the v0.2 gate. New readers recognize
v0.6 without rewriting historical records.

## Focused acceptance cases

- Pin the new question ID/text and canonical bytes/hash; prove the old v0.1
  question and archived receipt/outcome validation are unchanged.
- Two independently verified facts directly support one event: the model
  nominates one witness, only that ID is bound, and Host does not choose it.
- Directly relevant `observed_fact` candidates for the user-described event
  indicate competing identities or unresolved/conflicting identity: no witness
  is bound. A date on another fact cannot fill the selected witness's missing
  date.
- Preserve existing listing, time, economic-hypothesis, Builder, EI and Core
  gates and the default/custom-route boundary.
