# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Current HEAD: resolve with `git rev-parse HEAD`; do not rely on a hard-coded
value in this file.

Product-direction baseline:
`365dcd5ab7c3661172061c852b26341a98a1fbff` — Align post-Milestone-3 product
direction.

Last completed implementation checkpoint:
current HEAD — `Implement expiration payoff-threshold evidence`.

Completed: Milestones 1–4; post-Milestone-3 product-direction alignment;
context-governance baseline; mode-based Strike / Delta discovery-generation
policy documentation.

Accepted product refinement: mode-based Strike / Delta discovery generation
is documented; implementation remains future work.

Current status: Milestone 4 deterministic exact-rational expiration
payoff-threshold evidence is complete after broad independent review and
targeted re-review.

Risk-budget and affordability status: the standalone contract is frozen by the
current clarification commit; implementation is not complete.

Next development gate: BUILD standalone structure-affordability evidence
against `docs/risk-assessment-contracts.md`.

Read first: `docs/current-checkpoint.md`, `docs/product-direction.md`,
`docs/project-state.md`, and `docs/mvp-spec.md`.

Exact contracts: read only the task-relevant contract, source, and tests from
the current HEAD.

Validation baseline: 848 full-suite tests; 365 market-data tests; 174 focused
transformation tests; 25 transformation exports; 64 `market_data` exports.

Candidate assembly, screening and report integration, position management,
services, providers, Event Intelligence, and discovery remain deferred.

Existing validation and export baselines remain unchanged.

This file is a navigation map, not a complete specification or history.
