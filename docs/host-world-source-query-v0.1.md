# Host World source-query separation v0.1

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
