# Host Event Source Facts v0.4

Status: FROZEN / INDEPENDENT CONTRACT REVIEW PASS / NOT IMPLEMENTED.

## Bounded correction

The user approved this narrow correction on 2026-10-16. An authenticated SEC
primary HTML filing may contain several legitimate dates and no SGML header.
Neither condition by itself invalidates an explicitly dated event statement.
This successor changes only occurrence-date preparation; v0.1–v0.3 helpers and
historical archives retain their meanings. EI, listing, source admission,
model prompts, budgets, public APIs and Direct Profile v0.4 are unchanged.

## Authority and selection

Retain v0.2's unique verified observed-fact description selection and all
same-run snapshot/receipt/hash checks. Preserve supplied context by identity.
Only try this extension when that selected fact has no resolved event date.
Retain the v4 parser's existing supported cover grammar without broadening it.
Require its exact source to be a revalidated existing SEC primary-HTML
admission (`sec-edgar-cover-layout-v4`, version `4`), with matching source ID,
locator, body, retrieval time and hashes. Use the authenticated cover's unique
registrant anchor and canonical SEC archive CIK/accession locator; an extracted
body under an SEC-looking URL or an unrelated admitted cover is insufficient.
Date authority does not establish listing/security identity.

## Explicit occurrence grammar

Within the selected claim's unique exact original quote, require exactly one
complete dated occurrence statement, with ASCII whitespace folding only:

`On <full English month> <day>, <year>, <exact cover registrant> <action>.`

An optional immediately following explicit `(the “Company”)` or
`(the "Company")` alias declaration is permitted after that registrant; it
does not authorize a different subject. Actions are the existing completed
verbs `entered into`, `completed`, `closed`, `executed`, `signed`, `announced`,
plus the narrowly explicit `issued a press release` announcement form.
The action object must be nonempty and at most 240 characters. Reject negation,
modal, planned, conditional or hypothetical acts; reject another date in the
same statement, ambiguous subjects/actions and compound acts. A statement
containing an inner act with a second date is always unresolved in v0.4,
even if a human could distinguish its role. It cannot substitute that inner
date for the outer announcement date.

Folded claim text must equal the matched complete original statement. This is
not a paraphrase/date inference rule. The selected quote must be the complete
unique catalog paragraph containing that statement. Require exactly one
verified supported `date` binding at `/claims/<selected index>/event_date`,
to the same source/hash and exact paragraph offsets. Its paragraph must
contain that same statement and explicit date token. Exact integer offsets
exclude Boolean values. `claim.event_date` must be exact ISO, equal the parsed
date, valid, and no later than the UTC observation date; it is a consistency
check, not the date authority.

Unrelated dates elsewhere do not invalidate this statement. Multiple dated
statements in the selected paragraph leave the date unknown. Across the whole
body, a second complete occurrence sentence with the same exact registrant,
action verb and ASCII-whitespace-folded action object is ambiguous regardless
of whether its date agrees. Do not invent semantic equivalence between acts.
Also reject case-insensitive line-start labels `Correction:`,
`Corrected event date:`, `Withdrawal:` or `Retraction:` and the exact sentences
`The foregoing statement is incorrect.`, `The foregoing statement is corrected.`,
`The foregoing statement is withdrawn.` or `The foregoing statement is retracted.`
anywhere in the body (case-insensitive, ASCII whitespace folding only).
These finite conservative guards supplement, not replace, the already
required semantic verifier's conflict/uncertainty judgment. They do not
claim general cross-document contradiction detection. Do not choose the
first date, a report/filing/publication timestamp or a future deadline. The
finite grammar may conservatively decline unsupported prose; it must not
claim to resolve all narrative conflicts. In particular, known ambiguity in
the selected source cannot be ignored merely because it is outside a quote.

## Output and non-authority

On success return the existing singleton MethodologizedDateRange. Methodology
must record `host-event-source-facts-v0.4/sec-primary-html-occurrence-date`,
admission provenance, registrant/CIK/accession, source ID/hash/locator, action
role (announcement versus completed act), matched statement, original paragraph
and binding spans, and original date-token subspan. Offsets always address
unchanged source text, not folded text. No expected impact end, reassessment,
maturity authority, underlying identity, hypothesis or EI acceptance is created.

## Review and tests before the sole normal Event run

Independent contract review identified cross-paragraph equivalence and
inner-date ambiguities; the finite guards and unconditional second-date
rejection above resolve them before BUILD. Tests must cover the
normal source preparer with authenticated synthetic primary HTML, absent
SGML headers, unrelated dates, an exact completed announcement and full
paragraph binding. Counterexamples: URL-only fake origin, different cover/
issuer/source/hash, unverified fact or date binding, malformed/Boolean offsets,
paraphrased claim, publication-only/cover-only dates, modal/negated/future acts,
multiple/conflicting/corrected dates, wrong date role and inner-act attribution.
Keep legacy helper behavior and supplied-context identity unchanged. Review
actual implementation independently before one new normal Event operation
under the [existing fixed budget](normal-event-closure-2026-10-16.md).
