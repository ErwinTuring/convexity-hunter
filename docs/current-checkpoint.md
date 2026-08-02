# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Current HEAD: resolve with `git rev-parse HEAD`; do not rely on a hard-coded
value in this file. After finalization its subject is
`Clarify zero-input assembly lineage`.

Product-direction baseline:
`365dcd5ab7c3661172061c852b26341a98a1fbff` — Align post-Milestone-3 product
direction.

Last completed implementation checkpoint:
`9bf17c789daac33919e033ca08f8f05966bd7868` — Implement reviewed artifact
verifiability. The current documentation-only checkpoint is the zero-input
assembly-lineage clarification commit resolved from HEAD after finalization.

Completed: Milestones 1–5 and Milestone 6A; post-Milestone-3 product-direction
alignment; context-governance baseline; mode-based Strike / Delta discovery-
generation policy documentation.

Accepted product refinement: mode-based Strike / Delta discovery generation
is documented; implementation remains future work.

Current status: Milestones 1–5 and Milestone 6A — Reviewed Artifact
Verifiability are complete. Milestone 6A passed targeted independent re-review
after correction of all three accepted MAJOR findings. Milestone 6B —
Reviewed-Artifact Candidate Assembly remains unimplemented. Its initial formal
preflight was blocked by the contradiction between permitted zero-artifact
candidates and the existing one-or-more generic lineage-input contract. The
contract now clarifies `CalculationLineage.inputs` as zero-or-more, with `()`
the canonical empty representation; source and tests remain unchanged.

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
Rerun the existing formal read-only preflight task against the clarified
contract. This is not an implementation BUILD or a claim that 6B is ready.

Continue the existing PREFLIGHT task and rerun its formal analysis against the
clarified contract unless its context is no longer reliable; in that case
begin a fresh appropriately named PREFLIGHT session. Do not issue a 6B BUILD
prompt before the returned preflight report is evaluated.

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
