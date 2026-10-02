# Typed entity prompt and bounded Host resource profile v0.1

Status: **IMPLEMENTED — independent contract and final code review PASS.**
Production implementation was absent at contract freeze; the additive route
is now implemented. Existing routes remain unchanged. BUILD validation used
synthetic clients, not a new live product exercise.

## Evidence and scope

The [private replay](standalone-iren-private-replay-trial-2026-10-02.md) proves
two distinct issues for its capture: 24,090 wire bytes expand to 55,171 bytes,
over the old 40,000 internal budget; a claim entity reference item is an object,
while the unchanged schema requires a string. The v0.5 prompt says array but
omits the item type. Pure counterfactual semantic framing also exceeds the
80,000 request cap (102,050 bytes). None of these results is EI acceptance.

Correct only prompt specificity and caller engineering budgets. No schema,
catalog generator, source authority, coercion, evidence/temporal/EI rule,
receipt keys, model, economic policy or Core change. Invalid objects remain
invalid; no repair/stringification of the retained capture is allowed.

## Additive production target

Add immutable producer system prompt v0.6 derived from v0.5, specifying
`entity_refs` as an array of nonempty strings, never objects. Include one
explicitly format-only string example; it supplies no entity or source fact.
All other prompt obligations remain intact. Add v0.6 to the closed catalog
audit prompt-version allowlist while preserving exact selected/expected equality.

One additive direct-module runtime entry:
`run_host_grounder_same_run_evidence_catalog_v0_4`, with the same 11 named
parameters and result type as v0.3. It requires the existing context preparer,
selects v0.6 and existing fine diagnostics. No new resource parameter/API.
Private dispatch may grow; existing public parser/runtime signatures stay intact.

| Route | Producer prompt |
| --- | --- |
| v0.1 | v0.4 unchanged |
| v0.2 / v0.3 | v0.5 unchanged |
| new v0.4 | v0.6 |

At contract freeze, `run_host_grounder*` entry-point count was 5; implemented
count is now 6. Catalog `__all__` stays 9. Package-root exports remain unchanged.
Allowlist recognition alone never selects the new prompt or bypasses mismatch.

## Explicit caller resource profile

These are versioned finite engineering ceilings selected by Main, **not**
portfolio/risk/fee assumptions, data facts or economic calibration. No global
defaults change; callers must supply the profile explicitly through existing
client configs and `max_json_bytes`.

| Resource | Ceiling |
| --- | --- |
| Native HTTP response / model content | 40,000 bytes, unchanged |
| Discovery serialized request | 80,000 bytes, unchanged |
| Semantic serialized request | 131,072 bytes (128 KiB) |
| Internal JSON (`max_json_bytes`) | 1,048,576 bytes (1 MiB) |
| String / array | 8,000 bytes / 64 items, unchanged |
| Source body | 20,000 bytes, unchanged |
| Catalog entries / bytes / paragraphs | 64 / 32,768 / 128, unchanged |
| Output token budgets | discovery 8,000 / semantic 6,000, unchanged |
| Requests / timeout | one per role / 45 seconds, unchanged |

Wire remains independently checked against client output limits despite the
larger internal parser budget. Requests remain checked before HTTP invocation.
The 1 MiB ceiling is a processing budget, not a peak-memory guarantee or a
promise to admit every schema-valid expansion. Pre-output catalog-derived
completeness bounds for this source are 299,264 envelope / 3,011,904 verdict
bytes; the latter can exceed this chosen ceiling. Such cases fail closed.
The 128 KiB request cap may likewise reject large producer contexts. No
truncation, omission, automatic increase, retries, ranking or weaker validation.
Alternatives are retaining the old small ceilings (known operational blockage)
or supporting every theoretical expansion (larger processing/input exposure).
The chosen bounded MVP profile deliberately does neither. It is not fitted
to an option valuation result and establishes no investment claim.

## Validation / release gate

Focused tests: literal string-item prompt rule/example, unchanged legacy prompt
bytes/dispatch, new route/audit equality and unsupported-version rejection,
same signatures/counts, preparer requirement, object-item schema rejection,
independent wire/internal bounds and pre-invocation request overflow rejection.
Relevant Grounder regression, compileall, docs/diff checks and independent
code review must pass before commit/push. No model/source call during BUILD.
Any successor live exercise requires a separate preregistration and exact-hash
authorization; the retained invalid capture cannot become a passed product case.

Final validation: 19 focused catalog tests, 129 Host Grounder tests and the
full 1,650-test suite passed on the corrected v0.6-header implementation.
`compileall -q src tests` and `git diff --check` passed. Independent final
review verified legacy prompt bytes/dispatch, 6/9 API counts, the unchanged
11-parameter signature and independent resource limits. No source/model calls,
schema/default changes or Core economic-policy changes occurred during BUILD.
