# Convexity Hunter

Convexity Hunter researches exact supported long-option structures through
conditional payoff geometry, explicit cost/loss budgets, sensitivity and
repeat-loss policy. Underpricing is an optional stronger claim, not a
prerequisite for Core research; historical option data is not a Core dependency.

The thin Core application API supports World/Autonomous Discovery through an
injected source producer, Event Entry through an injected grounder, and Direct
Entry of an exact structure. World/Event branch accepted hypotheses and
deterministically enumerate eligible Long Calls, Long Puts or same-strike Long
Straddles without ranking or mandatory human selection. All entries use the
same Core. The system does not predict returns, recommend or execute trades,
or monitor positions.

## Current status

The new Core application is independently reviewed and tested. World/Event
return structured case sets and compact comparisons; full Chinese details are
rendered on demand from retained records. Direct Entry automatically renders
one full report. Missing required cost/risk inputs remain
`DATA_INSUFFICIENT_CORE`; missing optional valuation evidence alone does not.
Source producers/grounders and explicit caller research policy must be supplied
by the host. This is an application API, not a bundled autonomous search service
or a claim that all three live entry modes are operational. See the
[Core user flow](docs/core-convexity-mvp-user-flow-v0.1.md) and
[current checkpoint](docs/current-checkpoint.md) for runtime evidence and gaps.

### Retained legacy capabilities

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

ATM/Delta-based automatic Candidate Generation, non-expiration pricing
production, and a UI remain outside this Core MVP. Deterministic eligibility
enumeration is not a recommendation engine. The retained bounded offline
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
- [Core research doctrine](docs/core-convexity-research-doctrine-v0.1.md)
- [Three-entry Core user flow](docs/core-convexity-mvp-user-flow-v0.1.md)
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
