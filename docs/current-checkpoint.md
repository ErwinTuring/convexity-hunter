# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Current HEAD: resolve with `git rev-parse HEAD`; do not rely on a hard-coded
value in this file. After finalization its subject is
`Implement reviewed artifact verifiability`.

Product-direction baseline:
`365dcd5ab7c3661172061c852b26341a98a1fbff` — Align post-Milestone-3 product
direction.

Last completed implementation checkpoint:
resolve the current HEAD after finalization — Implement reviewed artifact
verifiability.

Completed: Milestones 1–5 and Milestone 6A; post-Milestone-3 product-direction
alignment; context-governance baseline; mode-based Strike / Delta discovery-
generation policy documentation.

Accepted product refinement: mode-based Strike / Delta discovery generation
is documented; implementation remains future work.

Current status: Milestones 1–5 and Milestone 6A — Reviewed Artifact
Verifiability are complete. Milestone 6A passed targeted independent re-review
after correction of all three accepted MAJOR findings. Milestone 6B —
Reviewed-Artifact Candidate Assembly remains unimplemented.

Risk-budget and affordability status: the frozen v0.1 contract is implemented
as a reviewed standalone capability. It is not candidate, screening, or report
integration.

Milestone 6 is now decomposed into Milestone 6A — Reviewed Artifact
Verifiability and Milestone 6B — Reviewed-Artifact Candidate Assembly. 6A is a
prerequisite for 6B. The canonical contract is
[`candidate-assembly-contracts.md`](candidate-assembly-contracts.md).

Completed Milestone 6A implementation: Volatility Environment, Tail Pricing,
and Structure Liquidity use exact incompatible v0.2 canonical contracts.
Their existing result fields and producer signatures remain unchanged; v0.1
wrapper instances intentionally reject. The contracts retain complete input
references, exact normalized evidence, public reconstruction values where
required, independently derived quality flags, and coordinated private
dependency verification. All 25 transformation exports, all 64 `market_data`
exports, their ordering, package-root exports, and public domain-record fields
remain unchanged. Historical Realized Volatility dependencies are completely
reconstructed, and calculation IDs are disjoint across complete dependency
and normalized-input closures. The exact contract is
[`market-data-contracts.md`](market-data-contracts.md#1324-milestone-6a-reviewed-artifact-verifiability-contract).

Next development gate:
`PREFLIGHT｜Milestone 6B — Reviewed-Artifact Candidate Assembly`.
This is a fresh formal read-only preflight against the existing assembly
contracts, not an implementation BUILD or a claim that 6B is ready.

Prepare the next formal preflight in the existing PREFLIGHT workflow unless
its context is no longer reliable; in that case begin a fresh appropriately
named PREFLIGHT session. Do not produce a 6B BUILD prompt before the returned
preflight report is evaluated.

Read first: `docs/current-checkpoint.md`, `docs/product-direction.md`,
`docs/project-state.md`, `docs/mvp-spec.md`, and
`docs/candidate-assembly-contracts.md`.

Exact contracts: read only the task-relevant contract, source, and tests from
the current HEAD.

Validation baseline: 179 focused transformation tests; 365 market-data tests;
32 focused risk-assessment tests; 885 full-suite tests; 7
risk-assessment exports; 25 transformation exports; 64 `market_data` exports.

Milestone 6B implementation, screening and report integration, position
management, services, providers, Event Intelligence, and discovery remain
deferred.

Existing validation and export baselines remain unchanged.

This file is a navigation map, not a complete specification or history.
