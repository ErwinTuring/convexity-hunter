# IREN fine producer diagnostic trial — 2026-10-02

## Preregistered boundary

One new attempt, not a replay of either spent producer trial. Use the reviewed
[fine diagnostics](host-grounder-producer-diagnostics-v0.2.md) runtime v0.3.
Retain the prior diagnostic trial's clarified questions, SEC-only model corpus,
identity references, fill-only preparation and acceptance gates. No source,
market-data, Core or trading calls; no retry or fallback. DeepSeek Flash JSON
mode, thinking off: discovery budget one/8,000 output tokens and semantic budget
at most one/6,000, timeout 45 seconds per request. Credentials remain external
and lazily resolved. Non-null unsupported impact windows stop before EI.

Experimental output adds only an **unvalidated structural census**: UTF-8 byte
length, lengths of the four fixed arrays (`claims`, `hypotheses`, `field_bindings`,
`coverage`) and booleans for exact root keys/schema/run/stage matching. Decode
is bounded at 40,000 bytes; inspection failure returns null. The observer returns
the original completion unchanged. No unknown keys, values, field paths, raw
payload or model prose are printed or persisted. Census counts are not verified
facts, accepted candidates or evidence authority. Closed failure labels are
reported without exception text. Actual role reservations use remaining budget.

## Frozen runner

Run ID: `iren-producer-diagnostic-fine-20261002-71e9cc71-6001-4a50-95ab-5422674fd9cc`.
Path: `/private/tmp/iren-producer-diagnostic-fine-20261002-71e9cc71-6001-4a50-95ab-5422674fd9cc/runner.py`.
SHA-256: `e4a26b815711b23a291be9733ca1a796532cdfe2451449c8be0a8758871aa10a`.
Immutable prior wrapper: `4ff01ce5cc74b85cad1f84ffe5f59902b113902a574e754e8b8f388c14e2952c`.
Immutable first helper: `4cda66a4d8d343f5da3ccf995dde498947d3456dccd2dc80bc67cb9d2a143de4`.
Only runtime/catalog production pins are updated:
`d5a4201e4aed105b878fde0214a861c785674b72423ee27ed498a81cee7cded4` /
`042adef52e443b8cd7db7c7f8a6ee92782b04a65fe7dd08d8fd96aba919eb437`.
All other module/source pins remain unchanged. New directory 0700, runner 0600;
exclusive new marker plus Main exact-hash gate precede any credential/model use.
Old files and markers remain untouched.

Default offline run passed: inherited producer/safe-field/Builder controls,
eight fine labels/four rejected diagnostic pairs, literal census controls,
five delegate pass-through controls and API compatibility. Six preparer
controls and synthetic Builder/EI route passed; zero credentials/source/live
calls. No new attempt/result exists at this registration point. Live execution
requires independent exact-hash safety PASS and preregistration commit/push.

No live product acceptance is claimed. Do not infer the old attempts' precise
failure from any new outcome or change validation bounds to force success.
