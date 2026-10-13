# Host Event Source Facts v0.3

Status: FROZEN / IMPLEMENTED / INDEPENDENT CONTRACT AND IMPLEMENTATION REVIEW PASS.

## Scope

Add one fail-closed SEC Nasdaq SRO accelerated-approval occurrence-date case
to the default Host fact preparer. Preserve v0.2 description-anchor selection
and all v0.1/v0.2 behavior; keep legacy helpers testable. This is a narrow
source-family grammar, not a general SEC, PDF, or prose parser.

Use only the normal same-run `HostSourceBody`, selected semantic receipt,
verified claim, and verified field-binding path. No source/model call, PDF
download/admission, prompt, budget, wire/schema, public API, listing rule, or EI
rule changes. Do not commit acquired SEC text or PDF fixtures.

The current Extract path can supply retained text, which Host hashes; it can
also supply incomplete or index text. The hash binds extracted text, not the
original PDF or SEC origin. Missing required structure stays unresolved.

Normal-path fit: Tavily Basic Extract returns `raw_content` for the requested
URL; Host requires that exact URL and retains it as `final_locator` with the
text and UTF-8 body hash. The catalog uses maximal nonblank-line paragraphs,
exposing only unique entries within limits (overflow fails, not truncates).
Producer `evidence_id` expands claims to entry source/locator/full quote and
bindings to entry source/full quote/start/end. Semantic receipt validation
checks the registered body hash and exact quote/span. No token entry is
produced; this amendment consumes full paragraph bindings and derives the date
subspan from the cover grammar. The existing DTO supports claim `text` and
`event_date`, a `date` binding, and supported paragraph evidence. The generic
prompt does not guarantee this SRO grammar, so success still requires the
exact allowed `claim.text`, correct entries, and one supported binding;
otherwise it remains unresolved. Incomplete text or excluded/overlong
paragraphs also remain unresolved. No admission, catalog, wire, schema, or
prompt change is part of this amendment.

## Eligibility and finite grammar

Use the same unique receipt-verified `observed_fact` selected by v0.2. Its
`claim.quote` must be the exact, unique full catalog paragraph containing the
complete operative clause below; a partial paragraph or clause-only quote is
not accepted. The full clause must be found uniquely within that quote and
unchanged source body. Receipt semantic validation remains mandatory. Define
ASCII-whitespace folding as replacing each run of ASCII whitespace with one
space and trimming; apply no case, punctuation, or other normalization.
Folded `claim.text` must exactly equal either the same matched complete
operative clause after folding, or
this sentence with the exact cover File No. substituted:

`The Securities and Exchange Commission approved the proposed rule change
(<exact File No.>) on an accelerated basis.`

`<exact File No.>` is replaced by the cover File No. No other wording,
paraphrase, subject, negation, or conditional form is accepted. This predicate
prevents a valid clause quote from being paired with a different claim.

Require the whole locator to match exactly
`https://www.sec.gov/files/rules/sro/nasdaq/<YYYY>/34-<RELEASE>.pdf`.
Reject userinfo, ports, query, fragment, percent-encoding, backslash,
dot/traversal or duplicate separators, extra path segments, non-ASCII path,
and any other scheme/host/path. URL year and release must equal the cover date
year and Release No.; File No. year is independent.

In that same retained body, require one ordered, unambiguous SEC cover block:

1. `SECURITIES AND EXCHANGE COMMISSION`;
2. One bracketed `Release No. 34-<RELEASE>; File No.
   SR-Nasdaq-<FILE-YEAR>-<FILE-SERIAL>` identity;
3. `Self-Regulatory Organizations; The Nasdaq Stock Market LLC;`;
4. Between the exact SRO heading and title, normalized ASCII whitespace is
   empty or exactly `Notice of Filing of Amendment Nos. <positive integer> and
   <positive integer> and`. No other title prefix is recognized. The values
   are grammar parameters, not release/date constants. Reject whole-word
   `DRAFT`, `PRELIMINARY`, or `PENDING` anywhere in the cover region,
   case-insensitively; the proposed-rule-change object remains valid.
5. Title `Order Granting Accelerated Approval of a Proposed Rule Change`;
6. One full-English-month date `<Month> <day>, <year>.` after the title and
   before the order narrative. Its date-token span excludes the final period.

Require one unique concluding operative paragraph before the Commission
signatory block. It begins `IT IS THEREFORE ORDERED`, identifies `the proposed
rule change (<same File No.>)`, and ends `be, and is hereby, approved on an
accelerated basis.` Require the exact completed-order title and clause; a
proposal, notice, recommendation, pending/conditional action, partial/index
text, conflicting disposition, duplicate identity, or mismatch is unresolved.
ASCII whitespace may wrap across extracted lines; quote checks and offsets use
the unchanged retained body.

Recognize across the whole body: full English month name or standard
three-letter English abbreviation (optional final period), ASCII whitespace,
one- or two-digit day, comma, ASCII whitespace, four-digit year; and ISO
`YYYY-MM-DD`. Every recognized token outside the exact cover-date span must be
a valid calendar date strictly earlier than the cover date, classified only
as a prior-date reference and never as evidence for another act. A same-day,
later, invalid, overlapping, or otherwise unclassifiable recognized token
leaves the result unresolved. Do not infer date roles from prose. No other
date format is interpreted or normalized; unsupported formats cannot
establish the cover date or binding evidence.

Outside the exact cover block, a case-insensitive line-start `Order date:`,
`Approval date:`, or `Dated:` label (optional leading ASCII spaces/tabs) makes
the result unresolved, even when its value is earlier. Do not apply v0.2's
one-date-per-body rule or add generic date-role inference.

Require exactly one envelope binding for `/claims/<i>/event_date`. It must be
verified and `supported`, role `date`, and use the same source ID and registered
body hash as the selected claim. Its quote/span must be the exact full catalog
paragraph containing the parsed cover date: `quote == body[start:end]`, with
exact `int` offsets (not `bool`), in bounds, and equal to the paragraph's
unchanged-body boundaries. The exact cover-date token span, excluding its
final period, must be fully contained in that paragraph span. Derive that
subspan only from the unique cover date already parsed by the cover grammar;
do not choose an arbitrary date within the paragraph. Existing catalog entry
uniqueness plus the exactly-one field-path binding rule remain required. The
binding quote is the paragraph, not a synthetic token quote; do not add a
second binding or new status.

`claim.event_date` must be a valid exact `YYYY-MM-DD` date equal to the cover
date, and no later than the UTC date of `observed_at`. The model date is
consistency-only. This separate cover-date binding is intentional: v0.2 anchors
its binding at the dated claim sentence, whereas this order separates the
cover date and concluding action.

## Result, tests, and limits

On success only, return the existing singleton
`MethodologizedDateRange(date, date, methodology)` and preserve supplied
context fields by identity; otherwise leave the date unresolved. Canonical
methodology JSON records rule version
`host-event-source-facts-v0.3/sec-sro-accelerated-approval-occurrence-date`,
source ID/hash/locator, Release No., File No., exact SRO name, date, the full
claim paragraph quote and its half-open span, operative-clause subspan, the
full binding paragraph quote and its half-open span, and exact cover-date-token
subspan. Record both paragraph spans and the contained clause/date spans
against the unchanged body; do not replace a paragraph span with its derived
subspan.

`The Nasdaq Stock Market LLC` is only this parser family's SRO identity; it
does not map to a ticker, Nasdaq, Inc./NDAQ, or `UnderlyingKey`. This result
does not create an impact end, `expected_window`, reassessment, maturity or
listing authority, impact/distribution hypothesis, or EI acceptance.

Use synthetic extracted-text fixtures only. Include a positive default-preparer
integration through actual catalog construction, producer normalization, and
validated receipt (not a hand-built-only binding): claim and date binding each
select their full containing paragraph. Assert methodology retains both
paragraph spans plus exact clause/date subspans. Also test multiple prior
full/abbreviated/ISO dates and independent File No. year;
unchanged v0.1/v0.2 behavior and v0.2 anchor; unsafe/mismatched locator;
duplicate/spoofed cover
identity or wrong SRO/title; title-only, truncated, proposed/conditional,
partial, missing/duplicate/mismatched clause or conflicting disposition;
claim-text/quote mismatch; unverified or wrong claim/binding/source/hash;
zero or duplicate event-date bindings; wrong quote/span/offset type (including
`bool`); invalid, disagreeing, or future claim date; outside-cover dates equal
to or later than cover, malformed recognized tokens, and explicit date labels;
partial/non-paragraph claim quote, binding paragraph not containing the cover
token, wrong paragraph boundaries, and cross-source/hash mismatches; and
synthetic default composition showing no call, budget, prompt, wire/schema,
export, or API changes.

No live request or replay is needed for this contract or its synthetic tests.
Without direct PDF admission, a counterfeit complete body under the canonical
locator cannot be distinguished from SEC-origin text. No launch or impact-end
date is established: commencement remains subject to SIP/Data Plan readiness
and a separate Nasdaq readiness filing becoming approved or effective. This
grammar and v0.3 default are the frozen build target. Implementation is in the
working tree and includes the synthetic catalog-to-normalized-receipt-to-
default-preparer integration above. Independent implementation review remains
pending; no live request, replay, commit, or restart was performed.
