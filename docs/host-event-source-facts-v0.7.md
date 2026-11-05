# Host Event Source Facts v0.7 — Declared Parent / Reference Date

Status: FROZEN / IMPLEMENTED / INDEPENDENT REVIEW PASS.

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

## Producer date-anchor output guidance v0.1 — 2026-11-05

Status: FROZEN / IMPLEMENTED / INDEPENDENT REVIEW PASS. This is output guidance only.
The user approved the smallest explicitly versioned Producer correction after
the retained IREN mismatch. The date authority above remains unchanged.

New normal Event/World Producer prompt identities are v0.12/v0.13, paired only
with unchanged Verifier v0.10/v0.11 respectively. Preserve earlier prompts,
versions and legacy/custom routes. Opt in only the normal default recipe;
do not add a public DTO, API export, source, model stage or call.

If existing evidence supports an observed event-occurrence anchor, instruct
Producer to preserve the exact complete original occurrence sentence as its
claim text, not a paraphrase, issuer substitution or combination of sentences.
Use its existing complete catalog paragraph evidence_id, without inventing
quote/offset DTO fields. Supply event_date only for that statement's explicit
supported occurrence date, with the existing indexed date-role binding from
the same paragraph. Host and the independent Verifier still decide whether
all existing source, date, role, identity, ambiguity and receipt gates pass.

Do not remove an in-sentence negation/qualification to force a match. Preserve
other material qualifications and counterevidence in appropriate existing
claims without appending unrelated sentences to the anchor. When the exact
witness/date/binding cannot be supported, abstention remains valid. Do not
infer dates from user input, filing/publication time or future milestones;
do not invent symbol, distribution mode, expected window or reassessment to
force acceptance; legitimately supported values remain allowed under their
unchanged contracts. Do not merge distinct financings, hard-code IREN, or
promise EI acceptance. Non-anchor
facts/interpretations retain their existing contracts. Format/binding repairs
reuse the same guidance within the existing two-call limit. No new live run
is authorized by this work unit.

Guidance implementation reuses the existing private orchestration with an
exact-Boolean opt-in, false for legacy/custom routes and enabled by the normal
default factory. Event/World share the same guidance. Audit/repair and archive
version registries recognize only the new exact Producer/Verifier/wire pairs;
World coverage binding is still mandatory. No public DTO/export or date parser,
Verifier wording, identity proof, EI/Core rule, configuration or budget changes.

Validation:346 related Host/Direct tests and35 runtime tests pass; the last
World closure-route fix passed a focused test and the archive fallback fix
passed all69 Store tests. Six prior prompt/notice hashes and two Event exports
remain unchanged; changed source/test compilation and diff checks pass.
Independent review identified the archive legacy-Verifier fallthrough; the
accepted fix rejects new Producers before that fallback and adds both negative
cases. Targeted re-review passes; no remaining review blocker. No live run or deployment claimed;
the historical IREN INCOMPLETE result is not changed by synthetic validation.

## Implementation validation (original v0.7 date rule)

The shared private date validator retains the unchanged v0.4 wrapper/policy;
only the normal v0.6 witness route attempts the new v0.7 fallback. Source
admission code and the two public Host Event exports are unchanged. Fixtures
exercise actual admitted v1/v3/v4 records, old/custom-route rejection, original
span provenance, supplied-context preservation and the closed negative cases.
Review identified a competing Parent definition outside the fixed prefix;
the final guard and counterexamples reject that ambiguity.

88 Host Event tests and 138 source-admission/World/Core/Direct/EI regressions
pass. Independent review passes with 8 focused old/new tests and additional
future-date, wrong-offset and non-exact-claim probes. Targeted compilation,
added-link/fence and diff checks pass; no full-suite or live compatibility
result is claimed. No deployment, paid operation or real EI/Core run occurred.
