# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Current HEAD: resolve with `git rev-parse HEAD`; do not rely on a hard-coded
value in this file.

Product-direction baseline:
`365dcd5ab7c3661172061c852b26341a98a1fbff` — Align post-Milestone-3 product
direction.

Last completed implementation checkpoint:
`86aee1dfa13cae0c865d8f24aa08754934abd540` — Implement hybrid scenario
valuation transformation.

Completed: Milestones 1–3; post-Milestone-3 product-direction alignment;
context-governance baseline; mode-based Strike / Delta discovery-generation
policy documentation.

Accepted product refinement: mode-based Strike / Delta discovery generation
is documented; implementation remains future work.

Current status: Development resumed. The revised Milestone 4 contract is
frozen by the current documentation clarification commit.

Next development gate: Milestone 4 BUILD of deterministic expiration
payoff-threshold evidence against the committed contract.

Read first: `docs/current-checkpoint.md`, `docs/product-direction.md`,
`docs/project-state.md`, and `docs/mvp-spec.md`.

Exact contracts: read only the task-relevant contract, source, and tests from
the current HEAD.

Validation baseline: 821 full-suite tests; 365 market-data tests; 147 focused
transformation tests.

Do not implement outside the accepted Milestone 4 scope. Provider integration,
Event Intelligence implementation, real option-chain integration, position
monitoring, and automatic trading remain prohibited.

This file is a navigation map, not a complete specification or history.
