# Standalone Host continuation — 2026-09-25

## Safe pause

Pause requested by the standing user policy when weekly quota reaches about 2%.
Freshly fetch and inspect Git on resumption; this note is not a static HEAD claim.
No new model call, Core run, market-data request, or credential change occurred.

## Tavily source transport: reviewed, live compatibility blocked

Local uncommitted `host_sources.py` and `test_host_sources.py` implement the
bounded Basic Search/Extract transport. Independent whole-module review passed;
the subsequent external-properties alias correction also passed targeted review.
Exactly one `api_key` or `TAVILY_API_KEY` is accepted; duplicates, mixed aliases
and unknown properties fail closed. No real credential is retained here.

The actual production-adapter experiment executed one predeclared Basic Search
and one single-URL Basic Extract, with no retry. Search concerned IREN's May 2026
SEC financing disclosure; extraction targeted the previously retained public
SEC document, not a newly selected result.

Both operations ended in `TavilyTransportError / UNKNOWN_RESPONSE_FIELD`.
Both local request reservations and both reserved credits were consumed.
Provider-reported credits and settled account usage were not established by
these rejected responses. No raw response was persisted. The unknown field and
its nesting level are **not identified**: do not guess, loosen parsing broadly,
or call this successful production retrieval/semantic verification/EI acceptance.

Earlier credential-path failures occurred before HTTP and are not remote retries.
The completed live two-operation budget must not be silently repeated. Next:
inspect the parser against the official response schema; if needed, explicitly
declare a separate minimal diagnostic operation retaining only safe schema
metadata, then fix and independently review a concrete discrepancy.

Validation this continuation: source 13 + model 18 + profile 6 = 37 tests PASS.
Prior continuation's correctly configured full regression: 1,489 tests PASS.
This is not evidence that the rejected live response is supported.

## Other retained work

`host_model` and `host_profile` remain committed and pushed from the previous
work units. Skill host/launcher development remains local and uncommitted;
it is not independently reviewed or accepted as operational. Preserve all
untracked implementation/test files and inspect them on resumption. Do not
commit unfinished Skill work together with a source compatibility correction.

The independent Grounder semantic gate, source-to-Core empty-batch host guard,
full cost/sensitivity policy work, persistence and Chinese workbench remain open.
No standalone three-entry MVP completion is claimed.
