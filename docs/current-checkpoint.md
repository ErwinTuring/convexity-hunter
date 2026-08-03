# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Current HEAD subject before finalization: `Clarify zero-input assembly lineage`.
After finalization, the implementation checkpoint subject is:
`Implement reviewed-artifact candidate assembly`.

Completed: Milestones 1–5, Milestone 6A — Reviewed Artifact Verifiability, and
Milestone 6B — Reviewed-Artifact Candidate Assembly. Milestone 6B passed
independent review after correction of one accepted MAJOR direct-construction
error-taxonomy finding and passed targeted re-review with no remaining findings.

The generic `CalculationLineage` now implements zero-input lineage with
canonical `inputs=()`. The public module
`convexity_hunter.candidate_assembly` exists with exactly two exports and
remains absent from package-root exports. Screening and report integration,
position management, providers, services, and the later application flow
remain deferred.

Final validation baselines:

- market-data tests: 366;
- market-data transformation tests: 181;
- candidate-assembly tests: 50;
- risk-assessment tests: 32; and
- full suite: 938.

API baselines:

- `market_data.__all__`: 64;
- `market_data_transformations.__all__`: 25;
- `risk_assessment.__all__`: 7;
- `candidate_assembly.__all__`: 2;
- `CandidateResearchRecord` fields: 17;
- `CandidateResearchRecordAssemblyResult` fields: 9; and
- `assemble_candidate_research_record` parameters: 21.

Next development gate: a fresh formal read-only preflight for the exact later
position-management-plan work unit already documented in
`product-direction.md`. No BUILD work for that unit begins before its preflight
report is evaluated.

This file is a concise navigation map, not a complete specification or
history.
