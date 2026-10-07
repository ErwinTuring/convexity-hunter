# Host Event Source Facts v0.1

Status: FROZEN / IMPLEMENTED / INDEPENDENT REVIEW PASS.

This bounded successor supplements [context preparation v0.1](host-grounder-context-preparation-v0.1.md).
Independent contract review passed. It adds no source/model call, provider,
prompt, EI schema, listing inference or acceptance relaxation. A validated
receipt proves linkage, not source truth. Unsupported inputs remain unknown.

## Description binding

When absent, bind the description only if exactly one receipt-verified
`observed_fact` claim names a retained source body. Multiple or zero such
claims leave it absent; no subjective choice or synthesized summary.
Preserve an existing description and all other context identities.

## Narrow SEC occurrence-date rule

Only the same unique fact may supply a singleton occurrence-date range:

- Use an already retained, hash-checked body. Require HTTPS `sec.gov` or
  `www.sec.gov`, exact EDGAR `/Archives/edgar/data/<CIK>/<accession>/<filename>`
  locator, no userinfo, query, fragment, non-default port, traversal or
  encoded path ambiguity. The filename is exactly one safe segment: no extra
  segments, encoded separators or dot segments. A domain alone is not evidence.
- The body must independently identify one consistent SEC filing form,
  accession, registrant and CIK. In this first bounded implementation use
  explicit SEC submission-header labels `CONFORMED SUBMISSION TYPE: 8-K`,
  `ACCESSION NUMBER:`, `COMPANY CONFORMED NAME:` and `CENTRAL INDEX KEY:`.
  Accession digits and CIK must match the locator. Conflicting or duplicate
  metadata stays unresolved; issuer identity must not come from model text.
- Require exactly one source sentence in the completed-action grammar:
  `On <English month> <day>, <year>, <registrant> entered into|completed|closed|executed|signed <act>.`
  The registrant is the exact header name, not a model-resolved alias. The
  sentence must be the unique verified fact's exact text and have a verified
  event-date field binding to that exact sentence/offset in the same body.
  Accept no generic semantic match, announcement/filing/publication label,
  planned action, modal/conditional action, additional date or ambiguous act.
- Parse the date from that source sentence. Its model event-date value must
  agree, but never supplies authority. Invalid/future occurrence dates relative
  to the context observation date, duplicate sentences, conflicting evidence,
  absent binding or malformed metadata leave the date absent.
- Methodology retains rule version, source ID, body hash, exact start/end
  offsets and locator. Reuse `MethodologizedDateRange`; do not invent new EI
  fields or hide provenance in an unbound model assertion.

Preserve existing date ranges by identity. No impact window, reassessment,
deadline, hypothesis or listing identity is created. In particular this rule
does not establish trading currency, share class or an `UnderlyingKey`.

## Validation and operational limits

Synthetic tests must cover a supported completed act, original identity,
metadata/URL mismatch, source/hash mismatch, rejected/unverified fact or date
binding, model/source date disagreement, future/invalid date, planned or
conditional action, multiple facts/sentences and preserved supplied fields.
Independent implementation review is required before commit.

This is deliberately narrow source parsing, not a general prose Grounder.
Most extracted filings may lack submission headers and remain unresolved.
No real acceptance, listing resolution or explanation of the earlier zero
hypotheses is claimed. No spent experiment is reopened.

## Implementation validation

The default preparer consumes the actual normalized v0.1 snapshot, not the
external v0.3 wire shape. A synthetic integration through `create_event_grounder`
tests producer, verifier, receipt and default preparation together. Supplied
description identity is preserved; another fact cannot lend it an event date.
English month parsing uses a fixed mapping, not the process locale.

Independent review's two findings were fixed: additional explicit dates anywhere
in the source body keep chronology unresolved, and case-variant duplicate SEC
header labels are rejected before canonical parsing. Targeted re-review passed.
Final focused coverage is 21 Event tests / 70 related tests. Final whole-suite
regression passed 1,808 tests in 308.972 seconds; the initial sandboxed
run's 26 loopback-permission errors are not a passing result.

This work crossed local execution dates 2026-10-05 through 2026-10-07, including
permission waits. No live provider/source/model acquisition was performed.
Builder recorded 0m47 preparation, 12m19 mixed implementation/test authoring,
2m03 validation, then 0m30 and 3m14 corrective passes. Independent initial review
recorded about 9m40. These are partial, overlapping role measurements, not a
whole-phase pure-coding percentage; the 70% implementation target is not proven.
