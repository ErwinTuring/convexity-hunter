# Host World source-query separation v0.1

## Approved successor v0.2 — 2026-10-28

Status: user-approved target, frozen for the bounded BUILD; not a claim of
implemented or deployed runtime. The v0.1 record below remains historical.

Replace only World's exact-original-query rule with this literal template:

```text
Public company events for {scope} from {start} through {end} inclusive: explicit catalysts; narrative/belief shifts; second-order transmission.
```

`scope` is the unchanged original World input. `end` is the configured exact
`evaluation_date`, rendered canonical ISO; `start = end - 6 calendar days`.
The inclusive range contains seven calendar dates, including the evaluation
date. Freeze it from the executor configuration, never a wall-clock read
during a run. Example: 2026-10-28 gives 2026-10-22 through 2026-10-28.
These are retrieval bounds, not authoritative event dates, impact windows,
reassessment dates, maturity authority, provider as-of replay or proof that
all returned material belongs to the window. Existing evidence gates remain.

Preserve the original input for Skill, model context, request hash and journal;
preserve complete lead-enriched model context. No Native lead, model output,
ranking or retrieved result modifies the query. The three frozen Discovery
lanes are retrieval vocabulary only, not three guaranteed coverage claims.

Preflight the original scope and the complete formatted query before any
Skill/source/model call or budget reservation. The formatted query must be
valid UTF-8 and at most 400 characters. Unrepresentable date ranges or overflow
use the existing `world_source_query_invalid` result. Never truncate, split,
drop words or use an alternate query. Original invalid-input precedence stays.
Use exactly the same query for the existing one Basic Search and one Basic
Extract; all source/model/Skill budgets and EI/Core rules remain unchanged.

The detached World snapshot's `world_source_query_policy` has exactly five
fields: `schema_version="world-source-query-v0.2"`,
`basis="scope_three_lanes_seven_day_window"`, `max_characters=400` (exact int),
`full_research_context_preserved=true` (exact bool), and `evaluation_date`
(canonical ISO date string). v0.2 itself identifies this exact template and
window grammar. Reject extra keys, malformed dates, wrong types/values,
unknown versions, and use outside World mode. Continue reading v0.1 snapshots
unchanged; never rewrite old runs. Producer provenance becomes `world-v0.3`.
No database migration, new public callback/export, planner, provider or
credential mechanism is introduced. Ordinary Event and Direct are unchanged.

Validate literal query bytes/date boundaries, original/full-context identity,
400/401 formatted-query boundaries, UTF-8/date underflow, no calls on invalid
queries, per-run isolation, detached snapshots, old/new journal recovery and
mode rejection. Retain ordinary Event/Direct and accepted-branch regressions.
Independent review and proportional validation precede deployment and the
single user-authorized normal World acceptance. No positive result is promised.

Status: CONTRACT_FROZEN / IMPLEMENTED / VALIDATED / DEPLOYED.
Independent contract review passed on 2026-10-14.
Independent implementation review, 170 related tests, the 1,993-test complete
regression, compileall and diff checks passed on 2026-10-14.
One post-fix World operation persisted the policy successfully but was blocked
at model processing; deployment does not establish EI/Core or investment success.

This bounded Host-only amendment supersedes the context-preparation contract's
unchanged-source-request restriction solely for the World composition below.
It does not modify Kernel, EI acceptance, market data or research policy.

## Boundary

Tavily [documents a 400-character maximum Search query](https://help.tavily.com/articles/5504684071-optimizing-your-query-parameter).
World currently enriches its request with provisional native names/URLs, then
uses that entire research context as Search/Extract query. A valid short user
request can therefore produce an invalid provider request. This is a reachable
integration defect, not proof of the cause of a discarded historical failure.

- Source query is exactly the original World request, unchanged and unranked.
- Require exact nonempty string, no surrounding whitespace, valid UTF-8 and
  length at most 400 characters. World preflights this original request before
  any Skill subprocess, source/model call or transport-budget reservation.
  The private Grounder factory independently revalidates its bound query
  before its own calls. Never split, truncate or rewrite the request.
- HostSkill applies the same 400-character ceiling to the unchanged discovery
  argument; the pinned last30days 3.21.1 CLI imposes no narrower domain limit.
- Keep World's existing non-string/empty/whitespace-only `ValueError` guard
  first and unchanged. Additional query-invalid inputs return the existing
  structured empty Core run with closed reason `world_source_query_invalid`,
  no submissions/branches and no Skill or Grounder calls. Private query-bound
  factory rejection uses `HostGrounderRuntimeError("SOURCE_QUERY_INVALID")`.
- Use the identical bound query for the existing one Basic Search and one
  Basic Extract. Source/model budgets, URLs and evidence gates are unchanged.
- Full lead-enriched research input remains intact for `UserEventInput`,
  subquestions, models, canonical run-input hash and receipt binding.
- Provisional names/URLs remain hints, never authoritative facts or accepted
  hypotheses. No partial-source outcome is upgraded.

## Compatibility and audit

Use a private, per-producer-run query-bound factory. Public
`create_event_grounder` and its returned callback signatures/exports remain
unchanged, and ordinary Event behavior is unchanged. Do not rewrite HTTP bytes
after client accounting or infer a query by splitting context marker text.

World's detached configuration snapshot must declare policy
`world-source-query-v0.1`, exact-original-request basis, 400-character limit and
full-context preservation. Normal Host World wiring must retain this snapshot
instead of substituting Event's snapshot. The existing journal retains the
original request; together they determine the actual query. Permit one closed,
versioned World configuration-snapshot variant: existing `models`, `sources`,
`skills`, plus exactly `world_source_query_policy`. Its exact fields/values are
`schema_version="world-source-query-v0.1"`,
`basis="exact_original_world_request"`, `max_characters=400` (exact integer),
and `full_research_context_preserved=true` (exact Boolean). Reject extra keys,
unknown versions, wrong values/types and its use outside World mode. Preserve
legacy snapshot acceptance unchanged. `host_store.py` must validate this
variant on creation and recovery with the known run mode; no SQLite schema,
table, journal-event shape, catalog-sidecar or database migration is needed.
Older binaries may reject the new metadata variant; do not promise downgrade
compatibility or rewrite archived records. Keep the full model-input hash unchanged.
Version World's producer provenance to distinguish the successor semantics.

## Acceptance

Tests must exercise real composition with captured synthetic transports:
expanded context exceeds 400, Search/Extract receive the exact short request,
models/receipt retain the complete context, and all accepted hypotheses still
branch normally. Test 400/401 boundaries, malformed strings, no Skill or
Grounder calls on query rejection, query state isolation across runs, snapshot
detachment, Host snapshot
wiring, journal creation/recovery of both variants, rejection in Event/Direct
mode, legacy Event signatures/default behavior and unchanged budgets.
Unknown failure messages/codes remain private. No live operation during BUILD.
Independent contract and implementation review precede release.
