# Host Event Source Facts v0.1

Status: FROZEN / BUILD READY; production date resolver not yet implemented.

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
