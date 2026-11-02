# Host Event Source Facts v0.7 — Declared Parent / Reference Date

Status: FROZEN / BUILD AUTHORIZED; implementation not yet claimed.

## Approved boundary

The user approved this bounded date-authority correction on 2026-11-02.
Formal read-only preflight is READY. Only the normal v0.6 single verified
witness route may try this fallback after unchanged v0.4 fails. Preserve
legacy/custom routes, supplied context, historical results and v0.4 methodology.
This is an explicit successor, not a claim that v0.4 was implemented incorrectly.

## Source and declared subject

Use only that selected observed fact's same authenticated SEC primary source.
Revalidate the existing admission, source ID, canonical CIK/accession locator,
retrieval time, parsed body/hash and original anchors. Closed parser/version
pairs are `sec-edgar-cover-v1/1`, `sec-edgar-cover-layout-v3/3`, and
`sec-edgar-cover-layout-v4/4`. Require exactly one valid registrant anchor and
one exact registrant-marker anchor. Missing/duplicate anchors fail closed;
do not repair or promote parsers. Original raw bytes are not retained: this
uses existing client-issued admission evidence, not a new raw-response replay.

Recognize only a line-start declaration beginning
`Following previous disclosure by <full cover issuer> (the “Parent”),`
or its paired ASCII-quote form. The issuer alone may differ by ASCII letter
case and existing ASCII whitespace folding; punctuation, words and Unicode
confusables must not change. Require a single quoted Parent declaration in
the whole body, a unique matching declaration preceding the selected act,
and preserve its exact source span/text. A different, repeated or ambiguous
Parent declaration fails closed. No Company/other alias or cross-source map.

The selected complete occurrence sentence must use exactly
`On <full English date>, the Parent, as Guarantor, <existing completed action>.`
Retain v0.4's verbs, 240-character original object bound, negation/modal/
compound-action rejection, valid nonfuture occurrence date and exact
claim-text equality. Full source issuer and alias refer to the same actor;
duplicate same-actor/verb/object occurrences anywhere in the source must
remain ambiguous, including direct-issuer versus alias spellings.

## Sentence date versus paragraph reference

Keep the selected witness, full unique original catalog paragraph quote and
one independently verified supported `/claims/<index>/event_date` binding
with exact integer offsets, source, quote and date role. The supplied ISO
claim date must match the occurrence date; Host does not create that field.

The selected sentence must contain exactly its one occurrence date. At most
one additional date in the same paragraph is allowed, outside that sentence,
only in the explicit closed phrase `agreement dated as of <full English date>`.
That date must be valid and is recorded as a document-reference date, never
as the event date. Reject all other extra date roles/formats, inner dates,
additional dated occurrences, conflicting or duplicate event statements and
the existing correction/withdrawal/retraction markers. Dates elsewhere in
the source remain subject to existing duplicate/correction guards. This is
not general date extraction, cross-fact date borrowing or first-date selection.

## Output and non-authority

Emit the existing singleton MethodologizedDateRange, with rule version
`host-event-source-facts-v0.7/sec-primary-html-declared-parent-occurrence-date`.
Retain v0.4's source/CIK/action/statement/paragraph/binding/date-token provenance
and add cover registrant/marker spans, declared-issuer comparison basis,
Parent-definition span/text, occurrence subject, and any reference-date
span/text/role. All offsets address unchanged source text.

No source parser, prompt, DTO, Verifier, EI/Core threshold, listing authority,
expected impact window, reassessment, maturity policy or budget changes.
Event and World use the same normal preparer; Direct is unchanged. A resolved
event occurrence date alone does not establish a lawful hypothesis, listing,
time applicability, EI acceptance or current option availability.

Focused tests must exercise authenticated v1/v3/v4 admissions and the normal
single-witness route, old v0.4 rejection/preservation, exact provenance spans,
missing/tampered anchors or evidence, wrong/repeated aliases, case-confusables,
inner/arbitrary dates, wrong binding roles and duplicate/corrected acts.
Independent review and focused regression precede commit/push. No paid run,
deployment, private capture, case substitution or historical rewrite is
authorized by this correction.
