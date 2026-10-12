# Host Event Source Facts v0.2

Status: FROZEN / INDEPENDENT CONTRACT REVIEW PASS / BUILD READY.
Production implementation is not yet present at this contract-freeze checkpoint.

This successor changes only the default Host fact preparer's deterministic
anchor selection and narrow occurrence grammar. [v0.1](host-event-source-facts-v0.1.md)
remains the historical contract. No source/model request, prompt, wire, public
API, EI acceptance rule or listing authority is added or relaxed.

## Description anchor with multiple facts

Retain the existing receipt/run/hash/source and unique-quote checks. An
eligible fact is a verified sourced `observed_fact`, not interpretation.

1. Preserve a supplied description by identity. Resolve its date only from
   that exact eligible claim; another fact cannot lend it a date.
2. If absent and exactly one eligible fact exists, retain v0.1 behavior.
3. If multiple eligible facts exist, require exactly one `user_event_input`
   coverage item and exactly one matching receipt coverage outcome, both
   `supported`, with matching index and subquestion ID. Among that coverage
   item's explicitly listed claim IDs, exactly one must be an eligible fact.
   All listed IDs must be distinct, nonempty exact strings and verified claims;
   a missing, rejected or malformed root invalidates selection. The coverage
   gap must be absent (`null`); supported-with-gap is not a complete anchor.
   Bind only that fact. No dependency traversal, first-item choice, sorting,
   date preference, source preference or model-generated summary is allowed.
4. Missing/rejected coverage, duplicate IDs, zero or multiple covered facts
   leaves the absent description and occurrence date unchanged. Reordering
   claims or coverage IDs must not change the outcome.

Coverage supplies declared relevance, not factual authority or EI acceptance.
The source-backed fact and existing Builder checks remain required. A global
fact count alone does not establish the reason for a historical failure.

## Explicit announcement occurrence

Reuse all v0.1 SEC locator, submission-header/registrant, unique sentence,
whole-body date ambiguity, exact verified date binding, source hash, chronology
and uncertain-action guards. Add only the completed verb `announced` to the
existing completed-action grammar:

```text
On <English month> <day>, <year>, <exact SEC registrant> announced <act>.
```

This dates the announcement, not the announced transaction's completion,
implementation, regulatory approval, or market impact. A future/modal act,
another date or conflicting chronology still remains unresolved under the
existing conservative grammar. Source text must explicitly assert the dated
announcement; a publication timestamp/date label is insufficient.

Retain the exact selected claim and date-binding offsets. New date methodology
uses `host-event-source-facts-v0.2/sec-8-k-occurrence-date`, the parsed verb,
source ID/hash/locator and offsets. It creates no impact end, reassessment,
maturity authority, underlying identity, distribution mode or falsification.
Existing context fields retain their identities.

## Deliberately unsupported formats

General issuer IR/newsroom announcements lacking independently established
issuer identity and occurrence grammar remain unsupported. An official-looking
domain, news summary or model-selected issuer alias is not sufficient.
This bounded change does not add a general newsroom admission parser.

## Validation and migration

Keep v0.1 helpers/legacy behavior testable; dispatch the normal default to the
successor explicitly. Historical archives and spent experiments are unchanged.
Test multiple facts with unique covered anchor, ambiguous coverage, rejected
receipt outcome, supplied bindings, permutation independence, exact announcement
occurrence and publication-only/planned/issuer/date/hash/binding negatives.
Verify the actual default composition, unchanged budgets/call counts and public
API, then independently review implementation and run relevant regression.
No new live experiment is authorized by this contract.
