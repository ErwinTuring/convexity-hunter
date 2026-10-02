# IREN Host binding-map trial — 2026-10-02

Separate one-shot exercise of [binding correspondence v0.1](host-grounder-binding-map-v0.1.md),
released as `1f51bdd43625b372ff085732a642c2bd91586c1c`. This is not replay of
the spent [corrected-profile attempt](standalone-iren-corrected-profile-trial-2026-10-02.md).
Use opt-in runtime v0.5, producer v0.6, semantic v0.6 and its Host-generated
ordered binding map. Same pinned SEC corpus, bounded identity, clarified F1/F2
questions, preparer, strict receipt/Builder/EI and temporal rules. No source
refetch, market data, Core, retry, raw retention or inferred economic policy.

Preserve the explicit resource profile: request discovery 80,000 / semantic
131,072 bytes, content/HTTP response 40,000, internal JSON 1,048,576,
string/array 8,000/64, source 20,000, catalog 64/32,768/128. DeepSeek Flash JSON
mode, thinking off; one reservation per role, 8,000/6,000 tokens, 45 seconds
each. Map bytes consume the request budget. All overflow/rejections fail closed.

Run ID: `iren-binding-map-20261002-b18ef3ac-8cd7-44f0-b962-48046fa9a718`.
Runner: `/private/tmp/iren-binding-map-20261002-b18ef3ac-8cd7-44f0-b962-48046fa9a718/runner.py`.
SHA-256: `223fca80c140e117466a16c5529733969147f7c956737e3e622be0643c753fe2`.
Directory/runner modes 0700/0600. Exclusive marker precedes invocation; only
sanitized aggregates may persist externally, 0600. External credentials stay
lazy and never enter model/context/output. No old artifact is modified.

Actual offline PASS: 7/9/11 runtime/catalog/signature checks and two targeted
map/strict-rejection controls. Immutable predecessor/helper pins retain prior
offline proof; those heavier controls were not rerun in this new preparation.
Zero live/source calls, credential reads or raw retention. Independent exact-hash
safety review and preregistration push must pass before Main live authorization.
Clean HEAD/main/origin equality, pinned-release ancestry and unchanged production
and source/helper hashes are required. No live outcome is claimed at registration.

Independent exact-hash safety review: PASS. Reviewer checked the narrow delta,
immutable pins, private modes, one-shot marker/gates and sanitized-only output
without executing fixtures, calls or reading raw content.
