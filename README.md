# Convexity Hunter

Convexity Hunter is an investigation assistant for identifying concrete Long
Option Position structures that may deserve further research as potentially
underpriced positive-convexity opportunities.

It supports two product directions: discovery from world events through
Event Intelligence and real option-chain candidate generation, and direct user
entry of a structure to investigate. Both paths converge on one verified exact
Long Call, Long Put, or Long Straddle selected by the user. The system
organizes auditable evidence; it does not prove opportunities, recommend or
execute trades, or monitor positions.

## Current status

Milestones 1–3 are complete. The repository contains domain records,
deterministic screening and reporting, provider-neutral market-data contracts,
provenance, freshness and lineage controls, and reviewed market-data
transformations for researching an already-specified option structure.

Active discovery, Skill integration, real option-chain candidate generation,
the revised expiration 1x/2x/5x/10x payoff-threshold evidence, production
candidate assembly, non-expiration pricing production, position-management
plan integration, and the complete application flow remain future work.

The active product output is Chinese only. An English renderer remains
implemented for compatibility and possible future reuse, but English is not
part of the active product flow.

## Documentation

- [Product direction](docs/product-direction.md)
- [MVP specification](docs/mvp-spec.md)
- [Project state](docs/project-state.md)
- [Context governance](docs/context-governance.md)
- [Current checkpoint](docs/current-checkpoint.md)
- [Architecture decisions](docs/decisions/README.md)
- [Development workflow](docs/development-workflow.md)

## Development

Python 3.9 or later is required. Source code is under
`src/convexity_hunter`, with tests under `tests`. Checked-in reports and values
are synthetic fixtures, not current market analysis or trade recommendations.
