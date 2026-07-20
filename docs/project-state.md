# Project State

## Project objective

Convexity Hunter is an investigation assistant for identifying concrete long-option structures that may offer cheap positive convexity.

## Current milestone

Milestone 3: Define auditable, provider-neutral external market-data contracts before connecting live data sources.

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
- Typed evidence records implemented and validated for volatility environment, tail pricing, structure costs, and classified evidence.
- Liquidity and scenario-result records implemented and validated with leg-level volatility inputs.
- CandidateResearchRecord implemented and validated with cross-record consistency, bounded scenario losses, empirical support requirements, falsification, and human-review fields.
- Deterministic Markdown rendering and the first end-to-end synthetic candidate report implemented and validated.
- Milestone 1.1 completed: separate Chinese and English deterministic candidate reports now place a plain-language overview before fully auditable technical details.
- Deterministic screening policy v0.1 documented and reviewed with provisional thresholds, structure-specific scenarios, decision precedence, immutable version semantics, and canonical reason codes.
- Deterministic screening policy v0.1 implemented and validated with immutable policy and decision records, protected policy identity, canonical reason codes, strict decision precedence, scenario-ambiguity checks, and purpose-built synthetic fixtures.
- Milestone 2 completed: deterministic ScreeningDecision results are integrated into Chinese and English reports with policy provenance, localized canonical reasons, and explicit separation from CandidateResearchRecord.
- Provider-neutral market-data contracts v0.1 documented and reviewed, covering auditable provenance, normalized observation time, immutable corrections, Decimal units, canonical security and option identities, quote scope, observation schemas, freshness boundaries, and staged implementation.
- Milestone 3A.1 completed: immutable provider-neutral provenance, normalization metadata, canonical enums, and underlying and option identity records implemented and validated with fixed synthetic fixtures.
- Milestone 3A.2 completed: immutable provider-neutral underlying and option quote, option-contract reference, cumulative-volume, and open-interest records implemented and validated with fixed synthetic fixtures.
- Milestone 3A.3 completed: immutable provider-neutral implied-volatility, Greeks, underlying daily-bar, rate-curve-point, and dividend records implemented and validated with fixed synthetic fixtures.
- Milestone 3B deterministic freshness, correction-selection, and calculation-lineage contracts documented and reviewed, including canonical reason ordering, complete composite-source checks, calendar-date-gap semantics, revision-vector dominance, and canonical tagged-JSON serialization.
- Milestone 3B.1 completed: deterministic single-record market-data freshness policy, context, assessment, canonical reason handling, exact Decimal timing metrics, composite-source checks, and calendar-date-gap rules implemented and validated with fixed synthetic fixtures.
- Milestone 3B.2 completed: deterministic provider-correction selection implemented and validated with exact lineage matching, normalized revision components, correction-identity conflict handling, revision-vector dominance, canonical terminal reasons, and deterministic synthetic fixtures.
- Milestone 3B.3 completed: canonical calculation lineage implemented and validated with immutable input references, deterministic tagged-JSON parameter serialization, exact type boundaries, duplicate-key-safe validation, Decimal/date/datetime canonicalization, depth and cycle controls, and auditable calculation-lineage sidecars.
- Milestone 3B completed: deterministic freshness assessment, provider-correction selection, and canonical calculation lineage are implemented, independently reviewed, and validated with fixed synthetic fixtures.
- Milestone 3C.1 completed: deterministic provider-neutral semantic observation identity implemented and independently reviewed for all ten normalized market-data record types, with versioned canonical tagged-JSON keys, exact identity-field boundaries, provider-neutral provenance exclusion, and deterministic fixed synthetic tests.
- Milestone 3C.2 completed: deterministic per-record selected/fresh market-data binding implemented and independently reviewed, including complete semantic candidate-group verification, deterministic correction selection, explicit correction-context trust boundaries, authoritative freshness recomputation, deterministic validation precedence, and fixed synthetic tests.
- Milestone 3C.3 binding-set temporal-coherence contract defined, targeted-preflighted, approved, and committed; implementation has not started.

## Current task

Implement and independently review Milestone 3C.3 binding-set temporal coherence
against the approved contract.

Milestones 3C.1 and 3C.2 are complete and independently reviewed. The Milestone
3C.3 binding-set temporal-coherence contract has been defined,
targeted-preflighted, approved, and committed; its implementation has not
started. The current implementation baseline remains 515 tests passed and 39
public `market_data` names. The planned post-3C.3 public count is 42, but those
APIs are not yet implemented. No normalized-record schema change is required
for narrow Milestone 3C.3. Milestone 3C.4 relationship/group coherence,
Milestone 3C.5 deterministic observation selection, Milestone 3C.6
historical-series completeness, and Milestone 3C.7 transformations and
`CalculationLineage` remain unimplemented. Broad Milestone 3 remains
incomplete. No provider has been selected and no network access is authorized.
`market_data.py` remains independent of the evidence, report, and scanner
modules.

## Last validated checkpoint

- Checkpoint: Milestone 3C.2 complete
- Commit: `320e4288f8071a2ee263e33a0198e76585b78fc3`
- Tests: 515 passed
- Public `market_data` API: 39 names
- Milestone 3C.1 semantic observation identity complete
- Milestone 3C.2 per-record selected/fresh binding complete
- Milestones 3C.3 through 3C.7 implementation not started

## Next task

Complete independent review of the Milestone 3C.3 implementation before its
implementation commit.

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
- Markdown escaping before untrusted external narrative text is rendered
- global custom-policy registration or fingerprinting

Deferred does not mean rejected. These items remain outside the current milestone and may be reconsidered later.

## Open questions

- Which options data provider can supply reliable historical volatility surfaces?
- What exact historical lookback should be used for IV percentile and skew percentile?
- How should liquidity thresholds vary by asset class?
- Which world-event and narrative Skills are sufficiently reliable and auditable?
- How should repeated-bet affordability be defined at portfolio level?
