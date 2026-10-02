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
