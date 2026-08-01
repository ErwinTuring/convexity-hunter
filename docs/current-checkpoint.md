# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Current HEAD: resolve with `git rev-parse HEAD`; do not rely on a hard-coded
value in this file. It is a documentation-only Milestone 6 contract-
clarification commit. Its immediate documentation-only base was
`ca6cd88eeffeab53c728db10989deb5a9eea9b34` — Align milestone session naming
and handoff.

Product-direction baseline:
`365dcd5ab7c3661172061c852b26341a98a1fbff` — Align post-Milestone-3 product
direction.

Last completed implementation checkpoint:
`3c37c50923a0e3847730bce8b33a28f7d45af4ea` — Implement structure
affordability evidence.

Completed: Milestones 1–5; post-Milestone-3 product-direction alignment;
context-governance baseline; mode-based Strike / Delta discovery-generation
policy documentation.

Accepted product refinement: mode-based Strike / Delta discovery generation
is documented; implementation remains future work.

Current status: Milestone 4 — Deterministic Expiration Payoff-Threshold
Evidence and Milestone 5 — Standalone Structure Affordability Evidence are
complete. Milestone 5 passed broad independent review, correction of all
accepted findings, and targeted re-review.

Risk-budget and affordability status: the frozen v0.1 contract is implemented
as a reviewed standalone capability. It is not candidate, screening, or report
integration.

Milestone 6 is now decomposed into Milestone 6A — Reviewed Artifact
Verifiability and Milestone 6B — Reviewed-Artifact Candidate Assembly. 6A is a
prerequisite for 6B. The canonical contract is
[`candidate-assembly-contracts.md`](candidate-assembly-contracts.md).

Next development gate: fresh formal read-only preflight for Milestone 6A —
Reviewed Artifact Verifiability.

Conversation boundary: begin a new ChatGPT main conversation for Milestone 6A.
That conversation performs Repository Grounding and first authors the separate
Codex PREFLIGHT session name and complete preflight prompt; it does not execute
the formal preflight itself or produce a BUILD prompt before the returned
preflight report is evaluated.

Read first: `docs/current-checkpoint.md`, `docs/product-direction.md`,
`docs/project-state.md`, `docs/mvp-spec.md`, and
`docs/candidate-assembly-contracts.md`.

Exact contracts: read only the task-relevant contract, source, and tests from
the current HEAD.

Validation baseline: 32 focused risk-assessment tests; 174 focused
transformation tests; 365 market-data tests; 880 full-suite tests; 7
risk-assessment exports; 25 transformation exports; 64 `market_data` exports.

Milestone 6 implementation, screening and report integration, position
management, services, providers, Event Intelligence, and discovery remain
deferred.

Existing validation and export baselines remain unchanged.

This file is a navigation map, not a complete specification or history.
