# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Previous implementation checkpoint:

- HEAD: `81d69196011b9a3bbc7161c57a3c2d628ba53444`
- subject: `Implement reviewed-artifact candidate assembly`

This clarification checkpoint is titled `Define prospective position management contract`.

Completed implementation remains Milestones 1–5, Milestone 6A — Reviewed Artifact
Verifiability, and Milestone 6B — Reviewed-Artifact Candidate Assembly. The
existing 6B validation baseline remains 938 full-suite tests, with API
baselines of 64 `market_data` exports, 25
`market_data_transformations` exports, 7 `risk_assessment` exports, 2
`candidate_assembly` exports, 17 `CandidateResearchRecord` fields, 9
`CandidateResearchRecordAssemblyResult` fields, and 21 assembly-producer
parameters.

Position-management implementation has not begun. The first formal
`PREFLIGHT｜Position-Management Plan Contract` returned `PREFLIGHT RESULT:
BLOCKED` because product-contract choices were not frozen. The prospective
plan contract is now clarified in
[`position-management-contracts.md`](position-management-contracts.md).
The clarification freezes the product and architecture boundary without
assigning Milestone 6C or any other milestone number.

The next gate is rerunning the existing formal
`PREFLIGHT｜Position-Management Plan Contract`. No BUILD prompt may be issued
before that report is evaluated. Screening, report integration, monitoring,
and execution remain outside this work unit.

This file is a concise navigation map, not a complete specification or
history.
