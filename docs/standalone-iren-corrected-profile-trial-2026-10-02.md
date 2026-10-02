# IREN corrected-profile trial — 2026-10-02

## Separate one-shot protocol

Use the implemented [typed-entity prompt and caller resource profile](host-grounder-typed-entity-profile-v0.1.md)
from release `6aee8a6696af2e7da71b16d36af9b6e98c849f34`. This is a new
attempt, not a retry or repair of any spent trial. Reuse only the pinned retained
public SEC body and existing bounded Host identity/context. No source refetch,
market data, Core research, ranking, alternate model or fallback.

Select opt-in runtime v0.4 / producer prompt v0.6. Explicit budgets:
discovery request 80,000 bytes; semantic request 131,072 bytes; internal JSON
1,048,576 bytes. Native response/content stays 40,000 bytes; string/array bounds
8,000/64, source body 20,000, catalog entries/bytes/paragraphs 64/32,768/128.
DeepSeek Flash JSON mode, thinking off, one reservation per role, discovery
8,000 / semantic 6,000 output tokens, 45 seconds each. No automatic enlargement,
refresh, truncation or second batch if rejected.

**No raw model-output retention.** The previous single-capture permission is
spent. Credential resolution stays external and lazy; no secret enters model
context, output or Git. Persist only closed sanitized aggregate JSON externally
with mode 0600 in the private 0700 directory. Unsupported impact windows stop
before EI. Existing receipt, preparation, Builder and EI checks remain unchanged.
Missing cost/risk policy is not supplied by this exercise.

## Release gate

Before live, require actual offline controls, independent exact-hash safety PASS,
preregistration commit/push and Main authorization of the frozen runner bytes.
Require clean HEAD/main/origin equality, the pinned release as an ancestor and
unchanged production/source/helper hashes. An exclusive consumed marker precedes
any live invocation; old markers/files remain untouched. Operational failure
does not authorize a retry. Model parsing, receipt verification, submission
construction and EI acceptance are separate outcomes, not interchangeable proof.

## Artifact

Run ID: `iren-corrected-profile-20261002-498b46c4-3762-4e82-8988-95d783a0491a`.
Runner: `/private/tmp/iren-corrected-profile-20261002-498b46c4-3762-4e82-8988-95d783a0491a/runner.py`.
SHA-256: `8c6622c96252db8b435cff56695f0a1a22d78865352670d91c6fbbd5f0fe4aba`.
Actual offline execution passed: 6 runtime entries / 9 catalog exports /
11 runtime parameters, inherited fake-client/preparer and census controls.
Live model/source calls and credential reads were zero; no marker/result exists
at registration. Independent exact-hash safety review passed without executing
write fixtures, live calls or reading the private capture. The reviewer checked
the corrected ancestry/clean-state gate, immutable pins, consumed marker,
sanitized-only output, unchanged F1/F2 preparation and independent limits.
No live outcome is claimed at preparation.

## Actual outcome — attempt spent

After preregistration `b77c46d` was pushed, Main authorized the exact runner
hash and executed it once. One discovery and one semantic reservation were
consumed; source calls zero, no market data, no raw retention. It stopped at
`SEMANTIC_VERDICT_REJECTED`, stage `semantic_wire_parse`, check
`producer_binding_alignment`. No receipt partition, Builder or EI result.
No retry or automatic profile/schema change followed.

The production path reached the semantic call, so this trial progressed beyond
the earlier producer normalization/schema failure. Its unvalidated native
census is 20,589 UTF-8 bytes, 18 claims, one hypothesis, 32 bindings and four
coverage entries. Counts do not establish facts, semantic approval or EI
acceptance. Request input hash:
`0af5aa32b85ee1d196541abef94521d4a9f3231b6fac3df03c42239d911737d8`.

The consumed marker and sanitized result remain externally in the registered
private directory. Exact offending values are not retained; the failure check
locates the validation boundary, not the particular mismatch or its cause.
Further diagnosis is read-only against code, prompt obligations and existing
tests. Another live attempt is not authorized by this spent protocol.

Independent factual review passed. Sanitized result SHA-256:
`a066dab877eb7f23856f3a5eac3e86acd48b7fb4e904ee6a7b88c4f0a0fa832b`;
consumed marker SHA-256:
`7f32158643c4269638e71b4a59f14a2d54ef43fa4801f4e568c660330ab5c7a3`.
Both files are mode 0600. Production ordering establishes structural producer
validation before semantic invocation; no semantic receipt/Builder/EI was proven.

Read-only diagnosis found a concrete framing ambiguity: semantic prompt v0.5
asks for the same catalog `evidence_id` as the envelope binding, while the
normalized envelope supplied to it expands that ID into source/quote/span and
does not supply an index-to-ID map. The full catalog permits reconstruction,
so this does not prove impossible input or explain the exact live failure.
Count, index and supported-binding identity checks remain correct and strict.
One existing synthetic alignment test passed, including rejection of a different
valid catalog ID. The next bounded design is a Host-derived alignment map for
an additive opt-in route; no repair or relaxed validation of this result.
