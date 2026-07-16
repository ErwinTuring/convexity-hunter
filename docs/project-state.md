# Project State

## Project objective

Convexity Hunter is an investigation assistant for identifying concrete long-option structures that may offer cheap positive convexity.

## Current milestone

Milestone 1: Define and implement the MVP domain model before connecting real market or world-event data.

## Decisions locked

- The system searches for cheap positive convexity, not direction.
- The final candidate is an option structure, not merely an asset.
- Events and narratives create hypotheses; market data supplies evidence.
- The MVP uses three screening layers:
  1. volatility pricing environment,
  2. tail relative pricing,
  3. concrete structure validation.
- MVP instruments are long calls, long puts, and long straddles.
- No unsupported numerical Convexity Score.
- Candidate states are Reject, Watch, Investigate, and Data insufficient.
- LLMs may interpret evidence but may not generate numerical market data.
- The repository documentation is the source of truth.

## Completed

- Repository initialized and pushed to GitHub.
- Minimal Python package structure created.
- Project philosophy approved.
- MVP specification drafted and corrected.
- First MVP domain objects implemented and validated: CandidateState, OptionLeg, OptionStructure, and Scenario.

## Current task

Define the evidence records required by the three-layer screening model.

## Next task

Implement typed records for volatility environment, tail pricing, structure costs, and classified evidence.

## Deferred

- real-time market-data providers
- news and world-event Skills
- last30days-skill or similar narrative integrations
- Serenity Alpha investigation
- option-chain scanning
- LLM integration
- user interface
- automatic execution
- portfolio-level barbell monitoring

Deferred does not mean rejected. These items remain outside the current milestone and may be reconsidered later.

## Open questions

- Which options data provider can supply reliable historical volatility surfaces?
- What exact historical lookback should be used for IV percentile and skew percentile?
- How should liquidity thresholds vary by asset class?
- Which world-event and narrative Skills are sufficiently reliable and auditable?
- How should repeated-bet affordability be defined at portfolio level?
