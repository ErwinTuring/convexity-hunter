# Host World source-query separation v0.1

## Event-unit composition successor v0.3 — 2026-10-28

Status: CONTRACT FROZEN / IMPLEMENTED / VALIDATED / INDEPENDENT REVIEW PASS;
deployed as `3be8b93` for one approved live acceptance, which ended BLOCKED
(five provisional units, no EI submissions/Core cases). A later lossless
diagnostic-projection fix passes review/tests but has no new live proof.
See the current checkpoint for deployment and spent-authorization state. Main's read-only
integration preflight verified multi-submission `SourceSubmissionBatch`, fresh
per-call clients, and the existing context-free unavailable-branch serializer.
The archive row bound and exact Core limit result are preserved below. The
composition approval alone authorized no live run or increased spending;
the later single-batch authorization is explicit below. No positive EI/Core
outcome is claimed.

### Units and unchanged authority

Preserve the existing exact-name/URL deduplication and canonical neutral order
of native lead groups. Each group becomes one provisional research unit, NOT
a verified event, accepted hypothesis, recommendation, or proof that two
groups describe different real events. The unchanged single-event Grounder
may find no unique event and abstain. Do not infer independence from a name.
Pass the unchanged original scope plus ONLY that group's names/URLs using the
existing provisional-hint input grammar. Do not send other groups as competing
event input. Retain the exact original World object for the outer batch,
journal and common Core. Each unit receives a distinct same-run Grounder ID;
never rewrite returned submission facts, dates, listing identity or hypotheses.
Append only existing producer provenance; successor World producer is
`world-v0.4`. All produced submissions enter one existing `run_world_core`.
All accepted hypotheses branch under its unchanged limits and evidence gates.
Ordinary Event/Direct, Kernel, Builder and EI APIs remain unchanged.

### Retrieval query and versioned snapshot

Use the v0.2 literal scope/three-lane/seven-date query, followed for each native
unit by this exact suffix: ` Provisional event lead: {names}.` Here `names`
is canonical compact JSON of that group's existing ordered names. The scope
is still the unchanged original World scope, and dates remain configured
D-6..D. This suffix is a retrieval hint only, never verified event identity.
`full_research_context_preserved=true` means the full original scope and
complete names/URLs of that unit are preserved; other units are separate
inputs, not truncated material or investment-based exclusions.
Search and Extract within one unit receive the identical bounded query.
Validate all unit model inputs and full query UTF-8/400-character bounds before
any unit call; never truncate, rewrite names, or silently use a scope fallback
for an invalid unit. Mark that unit unavailable; independent valid units may
continue only after whole-batch capacity preflight succeeds.

The v0.3 World query-policy snapshot retains exactly the five v0.2 fields,
but uses `schema_version="world-source-query-v0.3"` and
`basis="independent_native_event_units_seven_day_window"`. This version fixes
the unit grammar, query suffix and reservation policy here. Preserve v0.1 and
v0.2 readers without migration; reject unknown keys/values or non-World usage.
If native discovery is empty or fails, retain the existing ONE bounded Web
scope fallback without suffix, explicitly disclose that fallback, and do not
claim it represents multiple independently verified events.

### Whole-run capacity, not a hidden selection rule

Reserve one request per model role for the existing Skill phase even if that
phase fails; never reclaim spent/unused reservations. For N planned units,
require N <= caller `max_submissions`, source request/credit budgets >= 2*N,
and each model-role budget >= 1+N before any unit source/model request.
Discovery per-unit allocation is `min(2, (total_discovery_budget-1)//N)`;
Semantic allocation is one per unit. Reserve allocations in advance; fresh
clients receive ONLY their allocation (source 2 requests/2 credits per unit).
Finite source `byte_budget` is divided by N with integer floor. Finite source
`time_budget_seconds` is divided conservatively across N using the existing
float-seconds representation; for N>1 round the quotient toward zero by one
representable step. N=1 retains the original caps; optional `None` stays
`None`. A nonpositive per-unit allocation blocks the whole plan before calls.
This preserves aggregate source byte/time limits as well as requests/credits;
per-request timeout limits and per-response limits are never increased.
Map the source client's existing exact `BYTE_BUDGET_EXHAUSTED` and
`TIME_BUDGET_EXHAUSTED` errors to the existing
`world_grounder_source_budget_failed` category; never infer these from an
ordinary timeout or exception text.
Never reset the entire configured budget for each unit, borrow from another
unit, transfer unused repair capacity, add retries, or increase token/timeout
limits. No Native score or retrieved content changes the plan.

If the entire plan cannot fit, call no unit Grounder: disclose the units as
unprocessed with deterministic IDs and fixed capacity reasons through existing
unavailable-branch presentation. No prefix, ranking or hidden truncation.
If the number of unprocessed units exceeds the existing archive unavailable-row
bound (sum of the caller's four count bounds), retain one explicit aggregate
unavailable plan instead, with exact decimal count reason
`world_event_units_unprocessed_count:N`. This is all-unprocessed disclosure,
not a retained prefix. Never widen archive bounds or claim N Core cases.
Invalid, failed or no-submission units also remain visible as unavailable,
not as EI rejections or classified Core research. One unit's ordinary failure
does not drop another valid submission; retain existing explicitly propagated
stamped runtime failures unchanged. Do not invent a new diagnostics platform.
For ordinary exceptions, retain that call's already allowlisted fixed
diagnostic categories in its own unavailable `reasons` array as well as the
existing global union. Never copy exception text, payloads or another unit's
categories. This is lossless projection through the existing public shape,
not a new acceptance rule/schema. Do not retroactively enrich old archives.
Archive and UI must round-trip these branches under existing bounded shapes.
If the shared Core itself returns its frozen `LIMIT_EXCEEDED` result, retain
that exact two-reason/zero-case/zero-unavailable shape: the whole downstream
run is blocked, not partially researched. Do not append Host unit rows there
or overwrite the Core limit reason. Per-unit detail is unavailable in that
exceptional aggregate-limit result; do not claim otherwise. Outside that
case, aggregate added Host unit rows if necessary to preserve the archive
bound, retaining their exact count. Under no circumstances remove Core rows
or change a classification to make room for Host rows.

### Required validation

Two different units must reach the real shared Grounder with disjoint hint
inputs and same original outer identity; all accepted hypotheses enter the
common Core. Prove reservations across success, failure and repair, no calls
on insufficient plan capacity, invalid-unit isolation, honest no-submission,
old snapshot recovery, SQLite/UI unavailable-branch round-trip, Web fallback
and Event/Direct regressions. Synthetic fixtures are not real-provider proof.

### Explicit World-only configuration budgets

The user subsequently approved ONE normal World acceptance, at most ten
planned units, source <=20 requests/20 credits and each model role <=11
requests INCLUDING Skill. This does not authorize repeated batches, changes
to token/timeout/byte caps, or increased Event budgets. A read-only inspection
confirmed the launcher supplies Event config to the World loader; changing
the shared external Event file would therefore be inappropriate.

Freeze the minimal additive `host-world-config-v0.2` external JSON shape:
the existing `schema_version`, `skill`, `bounds`, plus required
`grounder_budgets` with EXACTLY `source_requests`, `source_credits`,
`discovery_requests`, `semantic_requests`. Each is an exact positive integer,
not bool. Derive an immutable World-only copy of the supplied Grounder config
with ONLY those four request/credit fields replaced. Retain the original
Event object and all credential references, models, endpoints, fee flags,
token, input/output, byte, time and timeout settings. Resolve no credential
and make no calls while loading. Existing factory validation still applies.
Keep the v0.1 shape and identity behavior unchanged; the existing public
v0.1 schema constant/signature stays unchanged. Reject missing/extra fields,
unknown versions or invalid values through existing sanitized loader errors.
No new CLI, credential schema, provider or launcher wrapper is needed.

Tests must prove v0.1 compatibility, exact v0.2 closure, World-only override
with supplied Event config unchanged, unchanged credential/token/resource
settings and lazy construction. Only after validation/review may the private
World file be backed up and changed for the authorized ONE batch. Do not
modify the shared Event file or treat a saved cap as recurring authorization.

## Approved successor v0.2 — 2026-10-28

Status: user-approved contract; implementation, focused validation, independent
review and deployment completed. One authorized normal World acceptance was
BLOCKED / no submission; see the current checkpoint. This is not a real EI/Core
closure claim. The v0.1 record below remains historical.

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

## Historical v0.1 contract and implementation record

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
