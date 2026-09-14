# Convexity Hunter

Convexity Hunter is an investigation assistant for identifying concrete Long
Option Position structures that may deserve further research as potentially
underpriced positive-convexity opportunities.

It supports three product entry modes: Autonomous Discovery from a retained
EventCandidate batch, Event Entry from caller-prepared grounding and
hypotheses, and Direct Entry of an exact structure. All three modes converge
on one verified exact Long Call, Long Put, or Long Straddle selected by the
user. The system organizes auditable evidence; it does not prove opportunities,
recommend or execute trades, or monitor positions.

## Current status

Milestones 1–5 are complete. The repository contains domain records,
deterministic screening and reporting, provider-neutral market-data contracts,
provenance, freshness and lineage controls, and reviewed market-data
transformations for researching an already-specified option structure,
including Milestone 4 deterministic expiration payoff-threshold evidence.
Milestone 5 implements reviewed standalone structure-affordability evidence
for one already-specified supported structure. This risk-assessment module is
a standalone capability, not candidate assembly, screening, or report
integration.

The standalone, unnumbered Position-Management Plan Contract and the separate
Position-Management Plan Screening and Chinese-Report Integration work unit
are complete. Deterministic report rendering may optionally receive a verified
plan result and display it in the active Chinese report. The existing English
renderer remains compatibility-only.

Automatic Candidate Generation, live RTH evidence acquisition, non-expiration
pricing production, and a UI remain future work. The bounded offline
`ResearchCase` composition now joins the three entry modes, preserves their
existing evidence lineage, and converges on the existing reviewed-research
service. Monitoring, alerts, scheduling, recommendations, and execution remain
absent.

The active product output is Chinese only. An English renderer remains
implemented for compatibility and possible future reuse, but English is not
part of the active product flow.

## Documentation

- [Product direction](docs/product-direction.md)
- [MVP specification](docs/mvp-spec.md)
- [Risk-assessment contracts](docs/risk-assessment-contracts.md)
- [Project state](docs/project-state.md)
- [ResearchCase application contract](docs/research-case-application-contract.md)
- [Context governance](docs/context-governance.md)
- [Current checkpoint](docs/current-checkpoint.md)
- [Architecture decisions](docs/decisions/README.md)
- [Development workflow](docs/development-workflow.md)

## Development

Python 3.9 or later is required. Source code is under
`src/convexity_hunter`, with tests under `tests`. Checked-in reports and values
are synthetic fixtures, not current market analysis or trade recommendations.
