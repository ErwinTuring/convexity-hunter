# Host World source-query separation v0.1

Implementation ledger: the user subsequently authorized a bounded BUILD on
2026-10-29. The successor code is implemented; independent implementation
review and targeted rereview PASS, with validation limitations retained;
see the
[current checkpoint](current-checkpoint.md). The freeze record below preserves
the authorization/status at freeze time. It does not authorize live calls,
private configuration changes, deployment or an external acceptance run.

## Validated partial extraction — contract v0.1, 2026-10-29

Historical freeze status: CONTRACT FROZEN / SUBSEQUENT_BUILD_READY. Independent contract review
and accepted P2 request-tuple-binding re-review PASS. User authorized contract
design/review ONLY. Every new type/version/field below is a FROZEN TARGET,
NOT current runtime. Production implementation is ABSENT. No BUILD, config
mutation, deployment or provider/model request is authorized by this section.
Current strict behavior stays unchanged.

### Scope and admission invariant

World only; same Native URL allocation, scoped Search, Basic Extract, source
admission, shared EI/Core and all existing resource limits. Normal Event and
Direct stay unchanged. This amends source-coverage policy, not factual truth
or EI acceptance. Prior39da868f's four extraction failures have no per-URL
receipt retained; they are NOT reclassified as partial successes or evidence
that this amendment would have changed that result.

Implementation clarification: the audit inventories Extract outcomes, not
every body produced by the existing independently authenticated admission
and issuer-reference chain. Those existing gates remain mandatory and are
not replaced by audit membership. Original Extract-success body bindings
must still match exactly; neither a failed source ID nor its exact locator
may acquire evidence authority through an alternate admission ID. This does
not add a source family, bypass admission, or authorize new retrievals.

Use the existing typed Extract result and its complete request/result
partition. Revalidate even constructor-bypassed objects: exact types; public
URLs; unique ordered requested URLs; success and explicit failure sets
disjoint and exhaustive, no extra/missing/duplicate URL; exact URL-derived
source IDs for BOTH sets; requested/returned/failed counts, source ID order,
coverage status and receipt counts/IDs/operation agree. Derive status from
the checked sets, never trust its label alone. Success body must be nonempty
strict UTF-8 and hash to its exact Host body digest; metadata retains current
exact-URL rules. Preserve request-relative order within both outcome sets.
Host freezes the exact outbound Extract URL tuple BEFORE the call (complete
seed-plus-Search union, exact integer count1..L). Require result.urls to equal
THAT Host tuple in exact order; counts, partitions and audit rows are checked
against the retained Host tuple, not a request list supplied by the response.
A self-consistent COMPLETE subset that omits an actually requested URL fails.

Only a genuine provider-reported URL failure may be separated from validated
success bodies. Empty/invalid success bodies, wrong IDs, bad URL order/set,
contradictory counts, malformed responses and resource overflow invalidate
the WHOLE unit. Never relabel them as failed URLs to salvage a subset.
No body clipping, selective success filtering, retries, alternate URLs or
extra calls. Run admission/catalog/quote/binding checks on ALL success bodies;
any existing mandatory failure still fails closed. At least one valid success
is required before models; all-explicitly-failed (EMPTY) never enters models.

### Host-owned audit: exact target shape

One optional immutable `HostSourceCoverageAudit` on `HostBuildContext`; when
present it is complete, not partially populated. Canonical JSON payload:

```json
{
  "schema_version": "host-source-coverage-v0.1",
  "host_run_id": "exact-outer-http-run-id",
  "unit_id": "exact-host-planned-world-unit-id",
  "run_id": "exact-grounder-unit-run-id",
  "canonical_input_hash": "exact-unit-input-sha256",
  "status": "PARTIAL",
  "entries": [
    {"source_id":"url:<sha256>","locator":"https://example.org/a","status":"BODY_AVAILABLE","body_sha256":"<exact-body-sha256>"},
    {"source_id":"url:<sha256>","locator":"https://example.org/b","status":"FAILED","reason_code":"PROVIDER_REPORTED_FAILURE"}
  ]
}
```

Illustrative strings above are placeholders, not real digests or fixtures.
Root keys exact; each row has exactly its displayed variant's keys. Rows
follow complete request order. Status is COMPLETE (all success), PARTIAL
(both sets nonempty), or EMPTY (all explicit failure); recompute counts from
rows and compare to the typed result. SHA-256 is over canonical UTF-8 JSON
(sorted keys, compact separators, no NaN), excluding the digest itself.
`run_id`/input hash identify the GROUNDING UNIT, not the outer HTTP run.
The private covered executor receives host_run_id from the existing server
run creation and binds the exact planned unit_id before extraction. Both IDs
are hash-covered; archive/root ID and unit row ID must match them exactly.
Reuse current string/array/JSON bounds; at most L<=5 requested rows.
No raw API responses, failed-body placeholders, provider error text, cookies,
credentials, account IDs or fabricated publication/title metadata in audit.

If no trustworthy typed result exists, audit is absent/UNKNOWN, never EMPTY
or COMPLETE. Such a source failure cannot yield a covered positive result.
If typed EMPTY is valid, retain its audit with the unavailable outcome.

### Models, verification and EI

Freeze the audit before any model request; include the same canonical payload
and digest in Discovery AND semantic-verifier inputs. They must distinguish
retrieval outcomes from evidence. Only successful bodies enter source_bodies,
source admission, registry and evidence catalog. Failed rows may be read as
coverage metadata ONLY: no quotes, fact support, date, issuer binding or
field binding may resolve through them. Existing question `coverage` is not
repurposed into source coverage.

The new producer and verifier wires each require exact
`source_coverage_sha256`; missing/mismatched or cross-unit/run/input/body audit
binding fails closed before projection. The Host rechecks it against context;
an echo/hash is not proof of truth. Carry it through localization, all result
clones, Builder context and rejected/no-submission paths. Only after exact
binding may the new outer field be projected into the existing internal
Builder shape; do not synthesize EI fields. Legacy wires cannot authorize
the partial route.

PARTIAL must NOT imply absence of contrary evidence or a complete review.
Verifier must reject claims that failed URLs were read or that all requested
sources were checked. Counter-evidence review must state the reviewed scope
and known missing coverage, not fill a universal negative. If a required
fact/date/listing/window/reassessment/contradiction conclusion needs a failed
source, it remains missing unless independently supported by surviving,
normally verified evidence. Known unresolved contradictions stay unresolved.
Existing EI v0.2 deterministic acceptance remains unchanged: honest limited
coverage plus sufficient independent required evidence MAY reach ACCEPTED;
missing required evidence remains INCOMPLETE. Neither is guaranteed.

### Host transport and durable disclosure (no Kernel change)

Current CoreRunResult has no retrieval-audit channel. Do NOT put Tavily data
into Core/EI domain records, weaken exact return types or encode audit JSON in
reason strings. Add a private Host-only covered executor/result envelope:
`core_result: CoreRunResult`, `source_coverage_by_unit: tuple`. It invokes the
SAME existing World/Grounder/Core implementation, not a second orchestrator.
Legacy public executor behavior stays strict and returns CoreRunResult.
The opt-in covered Host path must retain the envelope, not silently unwrap
and discard coverage; wrong/missing envelope fails before publication.

Each unit row has exact keys `unit_id`, `source_coverage` (complete audit or
null/UNKNOWN), `submission_ids`, `case_ids`. Use actual execution identities
and context relations, never parse guessed IDs. Every returned submission
and resulting case maps to exactly one unit with a valid non-EMPTY audit;
missing/contradictory linkage invalidates the covered output. Source errors
without trustworthy receipts have null audit and no submissions/cases.
Here `case_ids` means numeric CoreCaseRecord IDs; unavailable source/EI
branches retain coverage through their actual unit/submission context, not
by inventing numeric cases or parsing case IDs. Valid EMPTY therefore has
empty submission_ids/case_ids while its unavailable unit still keeps audit.
Keep trustworthy audits for valid EMPTY, no-submission, EI-rejected and later
Core-failed results too; no audit omission merely because no case formed.

Collect audits immutably in the existing execution; do not add a callback
platform/database/table. Publish only after the sidecar and normal result
are atomically retained in the existing batch archive. Serialization/binding
failure is an explicit publication failure, never a successful bare Core
result. Successful and typed failure paths need a bounded Host-owned audit
transfer; invalid/transport paths disclose UNKNOWN, not invented URL outcomes.

JSON summary, compact case and lazy detail/report views expose source coverage
for the affected case, successful/requested counts and failed source IDs/URLs
with fixed reason codes. Chinese PARTIAL wording: “来源提取覆盖不完整；仅核验
已取得正文，失败来源未被视为事实或反证不存在。” Disclosure accompanies any
accepted/researchable partial case. Render from the archived sidecar, never
rerun research. It is NOT a new Core disposition, score or recommendation.

### Versions and compatibility: frozen successor contract

| Target | Frozen successor |
| --- | --- |
| External World config | host-world-config-v0.5: exact v0.4 fields plus required source_coverage_policy="VALIDATED_PARTIAL_V0_1" |
| World source/query/producer | host-event-source-snapshot-v0.4 / world-source-query-v0.5 / world-v0.6 |
| Query basis | independent_native_event_units_partial_source_coverage (same five query fields/template/dates/max400) |
| Discovery/verifier prompts | host-grounder-discovery-prompt-v0.11 / host-grounder-semantic-verifier-prompt-v0.11; retain all v0.10 safeguards |
| Producer/verifier wires | grounder-output-v0.4 / semantic-verdict-v0.5: current closed shapes plus required source_coverage_sha256 |
| World archive | host-batch-snapshot-v0.2: v0.1 fields plus source_coverage_by_unit |

Covered source/query versions are World-only and must be paired. v0.1–v0.4
external configs remain strict; they do not silently opt in. The new config
selects the private covered executor. Reject covered policy on an audit-less
legacy executor before paid work. Read all historical snapshots/archives as
before; absent historical coverage is UNKNOWN, not inferred complete. No
SQLite table migration or EI/Core contract/version/classification change.
Batch outcome v0.1 and EI audit v0.1 stay unchanged; new World archive carries
the sidecar. Legacy Event/Direct wires and archives remain valid.

### Adversarial acceptance matrix and next unit

BUILD tests must cover: complete success; valid mixed partition; missing
essential/contrary evidence; all failed; unreported/missing/extra/overlapping
URLs; wrong IDs/order/counts/receipt; empty/non-UTF8/oversized success body;
also a self-consistent COMPLETE result over a subset of Host's request;
failed-ID citations; cross-run/hash/body mutation; dropped partial audit or
wrong case linkage; mixed independent units; no-submission/EMPTY retention;
legacy records unknown; and every existing resource/no-retry guard.
All-invalid and all-failed cases must make zero model calls. A positive
synthetic case proves lawful flow only, not a real event/investment result.

Historical independent contract review PASS: SUBSEQUENT_BUILD_READY; stop before BUILD.
Next separately authorized work unit: implement this opt-in Host coverage
envelope, bounded audit, source gate and existing presentation/archive path;
focused adversarial/compatibility tests and independent implementation review.
No production code, test-fixture change, private config, real replay or new
external experiment belongs to this contract-only authorization.

## Native URL consumption correction — 2026-10-29

Status: Main bounded read-only preflight and freeze complete; IMPLEMENTED,
177 relevant tests/compile/diff PASS; independent review and accepted P2
provenance-pair fix re-review PASS. This is an explicit retrieval-policy amendment, not a claim that
the previous implementation violated its frozen hints-only contract. It is
not a new EI authority, provider, Grounder or paid-run authorization.

Evidence: retained run903d3b69's sole partial submission cites a generic
stock-catalyst tutorial; its two statements discuss an illustrative industry
example, and its hypothesis acknowledges no specific event/issuer/date.
EI INCOMPLETE is lawful. Eight focused existing EI/anchor/Builder checks pass;
no Builder field-loss defect established. Other four no-submission causes
remain UNKNOWN. Code separately proves Native URLs are only model hints;
the current Search→Extract path need not read them. That is a product gap,
not proof of the cause of every historical failure.

For each Native unit, pass its complete exact-deduplicated URL tuple through
a private World-only factory argument (default empty for compatibility).
Validate all seeds with the existing public-URL guard BEFORE paid source
calls. Let L=min(max_extract_urls, max_array_items, 5). More than L seeds or
unsafe/non-string seeds reject the unit before its source/model calls; do not
keep a prefix. Native URL order is existing neutral lexical order.

Reserve all seeds first. If seeds<L, make ONE existing scoped Search with
max_results=min(max_search_results,L-seeds). Keep all returned results in
provider order, deduplicate by exact URL against seeds, and do not refill
unused slots. If seeds=L, skip Search. Then ONE Basic Extract reads the
entire seed-plus-search union; any missing/failed extraction rejects the unit,
not a surviving prefix. Zero seeds preserves the current bounded Search→
Extract behavior. Both paths still reserve at most2 Tavily requests/2 credits
per unit; total World budget allocation, source bytes/time, admission-client
limits and all model/catalog limits stay unchanged. No extra requests/retries.

Do not manufacture Search-result records for Native seeds. Extract supports
URL-derived source IDs without source_refs; use that existing path for this
World policy. Match IDs to exact URL hashes. Only actual Search references
may supply their title/publication metadata by exact URL; seed-only title and
publication remain unknown. Never derive event dates from these metadata.
All bodies still go through existing source admission, catalog/hashes,
semantic verification, binding, Builder, shared EI and Core. Native URLs and
names stay unverified hints; reading them does not authenticate their claims.

Version World producer as world-v0.5 and five-field query-policy snapshot as
world-source-query-v0.4, basis
independent_native_event_units_seed_urls_plus_search. Template, scope, seven
UTC dates, max400 and full research context remain unchanged. Use same-shape
source snapshot host-event-source-snapshot-v0.3 ONLY for World; it describes
the seed-plus-search policy including empty-seed fallback. Preserve reading
all historical snapshots; normal Event source policy and Direct unchanged.
No database schema migration. Persist actual policy, not a replay label.

Focused tests: all seeds consumed despite unrelated search results; seed-only
metadata unknown; exact URL/hash mapping; neutral complete union/dedupe;
fixed search allocation, no refill, full-capacity skip; invalid/private/too
many seeds fail before calls; partial Extract fails closed; fallback/normal
Event unchanged; all-unit budget preflight/no hidden prefix preserved;
World-only snapshot validation and historical persistence. Synthetic source
and model fixtures only. Independent review and focused relevant regressions
must pass before commit. No live replay or new external batch in this unit.

## Approved bounded entry-capacity correction — 2026-10-29

Status: CONTRACT FROZEN / IMPLEMENTED; 74 focused tests, compilation and
diff-check PASS; independent Luna review PASS. Main completed the bounded
loader/catalog/runtime preflight. User approved handling the catalog-entry capacity boundary.
This approval is not a fresh external batch authorization; prior live grants
remain spent. No private config change or paid request in this work unit.

The generator enforces BOTH max_catalog_entries and the shared
run_input_bounds.max_array_items, currently128. Raising only the former is
ineffective. Add external `host-world-config-v0.4`: exact v0.3 root shape plus
required `catalog_entries`, exact non-Boolean int in [1,256]. World-only copy
sets max_catalog_entries to that value and max_array_items to
max(original max_array_items, catalog_entries); reject an original array
bound above256 for v0.4 rather than silently lowering it. The array capacity
also bounds source/producer/verifier arrays, not only catalog entries. This
is an explicit resource allowance, NOT additional factual authority or any
relaxation of per-item verification, binding, source admission, EI or Core.
v0.1/v0.2/v0.3 semantics, exported v0.1 constant and loader signature remain.

Use256 as a bounded twofold capacity allowance, not a measured claim about
lost historical payload counts or a guarantee of success. Retain catalog
bytes65536, scan ceiling1024, source-body20000, input80000/262144, all other
byte/string/token/time/request/credit limits and paragraph/exclusion grammar.
Do not change the generator, truncate/coalesce/filter evidence, rank sources,
select a prefix or retry. Byte and remaining capacity overflows fail closed.
Existing persisted grounder_limits records both changed limits; no new Store
schema or diagnostic framework. Event config/credentials remain untouched.

Tests must prove strict shape/range/type and legacy compatibility; exact
immutable World-only overrides; lazy construction; 129 complete entries can
pass256 when bytes fit; 256/257 boundaries isolated with explicit synthetic
byte allowance; default64KiB byte failure still occurs without partial output;
unchanged source hashes, canonical bytes and evidence IDs for already-valid
catalogs; and persisted actual limits. Synthetic success is not live proof.
Focused validation and independent review precede commit/push. No automatic
deployment of expanded private caps and no new external experiment authorized.

## Approved bounded scan-capacity correction — 2026-10-28

Status: CONTRACT FROZEN / IMPLEMENTED / independent review PASS; 68 focused
tests and 2 Store snapshot/recovery tests PASS, compile and diff checks PASS.
User approved this correction and ONE subsequent
normal World batch under source20 requests/20 credits and models11 requests
per role INCLUDING Skill. No repeated batches or further automatic escalation.

The catalog counts scanned paragraphs BEFORE applying its existing nonunique
and overlong exclusions. A 128-scan ceiling can therefore reject a source set
whose complete eligible catalog still fits all existing evidence/input bounds.
Raise ONLY the World scan ceiling to 1024 for this bounded run. It is a CPU
resource allowance, not evidence authority, narrative duration or a promise
that sources/hypotheses fit. Retain entries128, catalog bytes65536, configured
source-body bound20000, Discovery input80000, Semantic input262144, all
run-input/JSON/string/array/token/timeout/source-byte/source-time limits, and
all source/hash/quote/field-binding/EI/Core checks. Do not change the catalog
generator or its paragraph/exclusion grammar, coalesce/crop sources, filter
claims to fit, or select a source/event prefix. Overflow still fails closed.

Add `host-world-config-v0.3` with the exact v0.2 four root fields plus required
`catalog_scan_paragraphs`: exact non-Boolean int in [1,1024]. Derive the
existing immutable World-only config copy with this one additional field
`max_catalog_paragraphs` replaced; retain v0.1/v0.2 semantics and public
constant/signature unchanged. No credentials resolved or calls during loading.
Event config/identity/caps remain unchanged. Existing source-snapshot
`grounder_limits.max_catalog_paragraphs` already records the actual value;
reuse that field and all existing readers, not a new audit/schema framework.

Prove old/new valid catalog canonical bytes and hashes are identical when the
old bound suffices; >128 scanned paragraphs with repeated exclusions can
produce the complete eligible catalog under1024; 1024/1025 scan boundaries,
entry/byte/array/hash guards remain fail-closed with no partial output. Prove
strict v0.3 shape/range, legacy identity and all other config fields unchanged,
detached persisted scan limit and lazy factory construction. Use synthetic
fixtures only. No historical raw-output reconstruction or retroactive labeling.
After focused checks and independent review, deploy via the original launcher,
back up the private World config, submit ONE normal World run, then preserve
the used config and restore original caps. Source/evidence/model failures are
results, not authority to increase a second bound or rerun.

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
