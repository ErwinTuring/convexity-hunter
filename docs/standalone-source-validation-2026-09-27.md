# Standalone Tavily transport validation — 2026-09-27

Scope: Basic Search/Extract transport compatibility only. This is not semantic
source verification, Event Intelligence acceptance, World discovery efficacy,
or standalone three-entry product acceptance.

## Reconciliation and diagnostic budget

The [Sep25 checkpoint](standalone-host-resume-2026-09-25.md) retained two failed
production-parser operations. They were not repeated as an unchanged experiment.
Official Search/Extract documentation alone did not identify their unknown
fields. Two separately declared diagnostic operations were then performed:

| Operation | Actual unknown field | Observed type | Reserved credits | Reported credits |
| --- | --- | --- | --- | --- |
| One Basic Search, same IREN SEC financing query | `root.follow_up_questions` | null | 1 | 1 |
| One Basic Extract, retained SEC filing URL | `root.results.items.title` | string | 1 | 0 |

No automatic retry, broader search, provider change or new model call occurred.
An Extract process-launch attempt used a mistyped working directory and never
started; it made no HTTP request. It is not a second provider operation.
Diagnostics retained field paths/types only; no response body, credentials or
account information were persisted. Failed-operation reservations are not
refunded. Reported credits do not establish settled account usage or quota.

These fresh responses identify concrete incompatibilities but cannot prove the
discarded Sep25 responses contained precisely the same fields.

## Narrow correction boundary

- Search may accept the optional `follow_up_questions` field only when null.
  It does not consume generated suggestions or change the query budget.
- Extract may accept an optional string `title` on success items; the title
  does not establish entity identity, source authority or factual verification.
- Other unknown fields and invalid types still fail closed. Source bodies and
  snippets remain separate and unverified.

Independent whole-module review and targeted compatibility review passed.
Source tests: 19 PASS; combined source/model/profile tests: 43 PASS.

## Post-fix bounded production validation

One separately declared Search plus one Extract (two-request/two-credit upper
bound) completed, without retry:

- Search: three source references, all `verified=False`; one reported credit.
  Results included another period/year's filing, so response success does not
  imply relevant or temporally correct facts.
- Extract: one body, 9,420 UTF-8 bytes, zero failed extractions, `verified=False`;
  zero reported credits against one retained reserved credit.
- Body SHA256: `89536ce6ff75b3e03c926b65c18c61995de4a9dd3456db9b8118bff92d186c2d`.
- Both local request and credit budgets ended at zero. No account-usage polling
  was performed; no settled remaining quota is claimed.

The two diagnostic operations and two post-fix operations total four reserved
credits and two provider-reported credits this continuation. The Sep25 failed
operations remain separate historical reservations. No raw body was persisted.
`COMPLETE` here denotes transport result coverage only, not semantic completeness.

Result: production Tavily transport compatibility is demonstrated for these
responses. Independent semantic Grounder, EI and full Host acceptance remain open.

Official references inspected during diagnosis:
[Search](https://docs.tavily.com/documentation/api-reference/endpoint/search),
[Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract).
