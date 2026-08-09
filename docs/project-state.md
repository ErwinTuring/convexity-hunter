# Project State

## Project objective

Convexity Hunter starts from changes in the world, identifies events that may
alter future return distributions and potentially affected underlyings,
constructs actual supported Long Option Position candidates from real option
chains, lets the user select one exact structure, and uses auditable evidence
to investigate whether its positive convexity may be insufficiently priced and
whether maximum loss fits explicitly declared risk assumptions. A direct user
entry path converges on the same verified exact structure and Convexity Engine.
The system identifies structures worthy of further investigation; it does not
prove opportunities, recommend trades, monitor positions, or execute trades.

## Current milestone

Milestones 1–5 are complete. Milestone 4 — Deterministic Expiration
Payoff-Threshold Evidence implements exact-rational thresholds for the
supported Long Call, Long Put, and Long Straddle grammar. Milestone 5 —
Standalone Structure Affordability Evidence implements reviewed standalone
affordability evidence for one already-specified supported structure.
Milestone 6 is contractually decomposed into 6A — Reviewed Artifact
Verifiability and 6B — Reviewed-Artifact Candidate Assembly. Milestone 6A is
implemented and passed targeted independent re-review after correction of all
accepted findings. Milestone 6B is implemented, independently reviewed,
corrected for one accepted MAJOR direct-construction error-taxonomy finding,
and passed targeted re-review with no remaining findings. Its initial
zero-artifact preflight blocker was resolved by making generic lineage inputs
zero-or-more while preserving methodology-specific exact-input verification.

## Milestone 6B completion checkpoint

The base clarification commit is
`abde4a0309afef070a28ea8f8774c337d36fbd67` (`Clarify zero-input assembly
lineage`). Final implementation commit: resolve with `git rev-parse HEAD` after
finalization; do not guess the SHA beforehand.
Formal preflight became READY after canonical-schema completion. Implementation
used exactly three source and three test files. Independent review initially
failed on one MAJOR finding: exact-type constructor-bypassed wrappers leaked
raw `AttributeError`. A narrow required-field validation correction now returns
controlled `ValueError`; targeted re-review passed with no remaining findings.

Final validation passed 366 market-data tests, 181 market-data transformation
tests, 50 candidate-assembly tests, 32 risk-assessment tests, and 938 full-suite
tests. API baselines remain 64 `market_data` exports, 25 transformation exports,
7 risk-assessment exports, 2 candidate-assembly exports, 17 candidate-record
fields, 9 assembly-result fields, and 21 producer parameters. Package-root,
scanner, renderer, existing producer signatures, fixtures, and persisted
candidate-record compatibility remain unchanged.

The standalone, unnumbered Position-Management Plan Contract is also
implemented, independently reviewed, corrected, targeted re-reviewed, and
complete. It is not Milestone 6C.

The standalone position-management contract is complete. Its separate,
unnumbered Position-Management Plan Screening and Chinese-Report Integration
work unit is also complete. The deterministic offline single-structure service
is implemented and independently reviewed under the A-level contract in
[`offline-single-structure-service-contract.md`](offline-single-structure-service-contract.md).
It adds exactly three direct-module public names and zero package-root exports.
Its 12 focused tests and the 1,038-test full suite pass.

Deterministic Direct-Entry Exact-Structure Verification is also implemented
and independently reviewed under
[`direct-entry-exact-structure-verification-contract.md`](direct-entry-exact-structure-verification-contract.md).
It adds exactly two direct-module public names and zero package-root exports,
retains authentic reviewed cost and liquidity proofs for one exact caller
structure, and passed 10 focused tests and the 1,048-test full suite.

The Deterministic Direct-Entry Reviewed-Research Service is implemented and
independently reviewed under
[`direct-entry-reviewed-research-service-contract.md`](direct-entry-reviewed-research-service-contract.md).
It adds exactly two direct-module public names and zero package-root exports,
delegates exact verification, candidate assembly, screening, optional plan
creation, and Chinese reporting to their existing authorities, and passed 11
focused tests and the 1,059-test full suite.

## Position-management completion checkpoint

The base clarification commit is
`a41b35df797c0720410c548841c5bb456b20f2ce` (`Define prospective position
management contract`). The final implementation checkpoint is the current
repository HEAD with subject `Implement prospective position management plan`.
The exact implementation files are
`src/convexity_hunter/position_management.py` and
`tests/test_position_management.py`. The exact documentation files finalized
with it are `docs/position-management-contracts.md`,
`docs/product-direction.md`, `docs/mvp-spec.md`, `docs/project-state.md`, and
`docs/current-checkpoint.md`.

The standalone work unit provides 11 public module exports, the exact
assembly-retaining plan/result architecture, and the four-parameter producer.
Final validation passed 60 position-management tests, 366 market-data tests,
181 market-data transformation tests, 50 candidate-assembly tests, 32
risk-assessment tests, and 998 full-suite tests. Compatibility baselines are
64 `market_data` exports, 25 `market_data_transformations` exports, 2
`candidate_assembly` exports, 7 `risk_assessment` exports, 17
`CandidateResearchRecord` fields, 9
`CandidateResearchRecordAssemblyResult` fields, and 21 assembly-producer
parameters.

The implementation passed independent review after correction and targeted
re-review. No package-root, scanner, renderer, fixture, persisted-record, or
existing-producer change was made by the standalone contract. The downstream
integration changes only the renderer and its authorized tests. Monitoring and
execution remain absent. Both work units remain unnumbered and are not
Milestone 6C or Milestone 7.

## Position-management plan screening and Chinese-report integration checkpoint

Committed base:

- HEAD: `ab904d65c6d768b9db9df774621692a39245915f`
- subject: `Implement prospective position management plan`

Current finalized work-unit subject:

`Integrate position management plan into Chinese reports`

Do not guess the final work-unit commit SHA before committing. The work unit is
standalone and unnumbered, not Milestone 6C or Milestone 7. Its implementation
and test files are `src/convexity_hunter/report.py`,
`tests/test_report_rendering.py`, and `tests/test_candidate_assembly.py`.
The six finalized documentation files are `README.md`,
`docs/current-checkpoint.md`, `docs/mvp-spec.md`,
`docs/position-management-contracts.md`, `docs/product-direction.md`, and
`docs/project-state.md`.

The renderer has four parameters and accepts an optional verified plan result.
Plan rendering is Chinese-only for verified `WATCH` and `INVESTIGATE` plans;
the no-plan path remains compatible, and screening state remains separate from
research state. The final confirmation review passed. Final validation passed
55 report-rendering tests, 50 candidate-assembly tests, 48 scanner tests, 60
position-management tests, 366 market-data tests, 181 market-data
transformation tests, 32 risk-assessment tests, and 1026 full-suite tests.
Package-root exports and existing producer schemas remain unchanged. Monitoring,
alerts, scheduling, recommendations, and execution remain absent.

### Completed Milestone 6A implementation

Milestone 6A strengthens the existing Volatility Environment, Tail Pricing,
and Structure Liquidity wrappers without changing their result fields or
producer signatures. Their accepted identities are respectively
`volatility_environment` / `paired-atm-volatility-environment` / `v0.2`,
`tail_pricing` / `nearest-observed-delta-wing-tail-relative-pricing` / `v0.2`,
and `structure_liquidity` / `exact-structure-liquidity` / `v0.2`.

The exact v0.2 schemas are intentionally incompatible with v0.1. Current
producers emit v0.2 and direct constructors accept only exact v0.2;
v0.1 wrapper instances intentionally reject, with no migration, legacy
verifier, compatibility adapter, dual-version constructor path, or persisted-
artifact migration requirement.

The accepted retained-evidence boundary uses complete input references
(`record_id`, aware UTC `normalized_at`, and canonical ordered `source_ids`)
and exact direct normalized-evidence items that add role and permitted
propagated flags. Volatility v0.2 retains complete realized-volatility
dependency inputs plus exact direct current and historical evidence. Tail v0.2
requires intrinsically verified Volatility v0.2, retains exact direct tail
evidence, and uses a conflict-checking deterministic input union. Liquidity
v0.2 retains exact public structure identity, public-leg-ordered quote,
volume, and open-interest evidence, and exact independently recomputable
calculation values. Private wrapper verifiers reconstruct every public field,
lineage reference, chronology boundary, and quality flag from strict
byte-canonical tagged JSON.

The implementation was built against the clarified v0.2 contract and changed
only `src/convexity_hunter/market_data_transformations.py` and
`tests/test_market_data_transformations.py`. Volatility reconstructs the
complete embedded Historical Realized Volatility public record, exact input
references, and lineage before authoritative dependency validation.
Volatility and Tail enforce mutually disjoint calculation IDs across target
calculations, every embedded dependency calculation, and every normalized
input in the complete closure. Tests retain complete static literal v0.2 JSON
artifacts with full byte equality for Volatility Environment, Tail Pricing,
and Structure Liquidity, plus decisive dependency-mutation and actual
Tail/Scenario consumer-path coverage.

Tail production reuses the private Volatility v0.2 verifier, and Scenario
Valuation reuses the private Tail v0.2 verifier without changing Scenario
Valuation's public records, signature, identity, formulas, ordering, or
exports. The 25-name `market_data_transformations` API, 64-name `market_data`
API, their ordering, package-root exports, and public domain-record fields are
preserved. The canonical exact contract is
[`market-data-contracts.md`](market-data-contracts.md#1324-milestone-6a-reviewed-artifact-verifiability-contract).
The initial independent review failed with three accepted MAJOR findings:
incomplete Historical dependency verification, calculation-ID collisions,
and insufficient independent golden, mutation, and consumer-path coverage.
All three were corrected, and targeted re-review passed with no remaining
finding. Final validation passed 179 focused transformation tests, 365
market-data tests, 32 risk-assessment tests, and 885 full-suite tests. Public
API counts remain 25 transformation names, 64 market-data names, and 7
risk-assessment names. Later v0.1 references in completed checkpoint
narratives remain historically accurate descriptions of the code at those
checkpoints; they are not active Milestone 6A implementation targets.

## Decisions locked

- The system searches for cheap positive convexity, not direction.
- The final research unit is one exact verified option structure, not merely an
  asset or a multi-position optimized portfolio.
- Discovery entry and direct user entry are equal first-class paths and
  converge on the same Convexity Engine.
- Events and narratives create hypotheses; market data supplies evidence.
- Event-to-underlying mapping is Skill-led; Convexity Hunter owns the accepted
  input and audit boundary, not a competing mapping algorithm.
- Mature Skills should be reused where suitable, but native outputs, thin
  adapters or compositions, and the product's standard accepted input remain
  distinct because available Skills may satisfy only part of the contract.
- The MVP uses three screening layers:
  1. volatility pricing environment,
  2. tail relative pricing,
  3. concrete structure validation.
- MVP Long Option Positions are Long Call, Long Put, and Long Straddle.
- “Long” is position direction, not maturity; “长期权” is not a synonym.
- Standard monthly options use an initial versioned 30–150 calendar DTE policy,
  with 60–120 as the core range and expiration at least 30 calendar days after
  the expected event-window end. 0DTE and Weeklies are excluded.
- Strike and Delta discovery generation is mode-based, not universal.
- Extreme-tail mode uses 5–10 absolute Delta as primary, greater than 10
  through 15 as fallback, and 2–5 only as a qualified exploratory far-tail
  tier.
- Event-directional mode retains representative 10 and 25 Delta candidates
  without ranking.
- Bidirectional distribution expansion uses an ATM or near-ATM Long Straddle.
- 25 Delta is not globally rejected.
- Direct user entry is not rejected solely for being outside discovery-mode
  Delta defaults.
- Low premium does not establish cheap tail pricing.
- Extreme-tail scenarios require future mode-specific event-level, severe,
  and extreme coverage, but no single return multiple determines
  `Investigate`.
- No universal annual tail-protection budget is imposed.
- Candidate inclusion follows eligibility and layered user selection, not
  arbitrary absolute caps or automatic investment-attractiveness ranking.
- Expiration payoff-threshold evidence uses the exact ordered 1x, 2x, 5x, and
  10x multiples of expiration gross position value relative to total entry
  cost, exact rational threshold and move evidence, and explicit unavailable
  downside branches on the nonnegative underlying-price domain.
- Bearability depends on explicit caller risk assumptions; without them,
  absolute loss is reported and affordability is Data insufficient.
- The first report states monetization, reassessment, and exit conditions for
  later human judgment. The product does not monitor, alert, or automate exits.
- The active report is Chinese only and begins with a short beginner-facing
  overview. Implemented English rendering is retained but inactive.
- No unsupported numerical Convexity Score.
- Candidate states are Reject, Watch, Investigate, and Data insufficient.
- LLMs may interpret evidence but may not generate numerical market data.
- The repository documentation is the source of truth.
- Repository truth and grounded planning are mandatory for implementation work.
- Grounding is task-scoped and risk-proportional.
- Dynamic checkpoint content remains minimal.
- Conversation history is background, not an exact contract.
- Durable cross-cutting rationale is recorded through selective ADRs.
- Token minimization must not reduce factual grounding, but repeated irrelevant
  context is avoided.
- [Product direction](product-direction.md) is the canonical
  post-Milestone-3 product statement.

## Completed

- The context-governance baseline, current checkpoint, ADR policy, and ADR-001
  through ADR-006 are documented.
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
- Milestone 3C.3 binding-set temporal coherence implemented, independently reviewed with REVIEW RESULT: PASS, validated with 541 tests passed and 42 public `market_data` names, and committed and pushed in `1fd33889885cfa7e2e75853e2bb54b3c15260982` (`Implement market data snapshot timing assessment`).
- The broad standalone Milestone 3C.4 relationship/group-coherence contract was preflighted and found not yet viable because relationship groups, roles, cardinalities, result architecture, issue evidence, and compatibility matrices remain unresolved.
- Milestone 3C.4 is decomposed into 3C.4a auditable binding references, 3C.4b explicit relationship/group request representation, 3C.4c exact identity and comparable-session coherence, 3C.4d quote phase/scope/venue compatibility, and 3C.4e analytics/activity/contract-reference coherence.
- Milestone 3C.4a auditable binding references are implemented, independently reviewed with REVIEW RESULT: PASS, and validated with 559 tests passed and 45 public `market_data` names. It was the completed implementation checkpoint before Milestone 3C.4b.
- Milestone 3C.4b explicit relationship/group request representation is complete. The implementation adds exactly `MarketDataRelationshipGroupKind`, `MarketDataRelationshipRole`, `MarketDataRelationshipGroupMember`, `MarketDataRelationshipGroup`, and `MarketDataRelationshipRequest`, bringing the public `market_data` API to 50 names. It provides four versioned relationship-group kinds, seven roles, and three frozen structural artifacts, with exact structural grammar, cardinality validation, duplicate-reference control, deterministic canonicalization, and immutable request storage. The first independent review returned `REVIEW RESULT: FAIL` because it found five test-protection gaps and no implementation-behavior defect. All five test findings were corrected without changing the source implementation. The targeted independent re-review passed with `TARGETED RE-REVIEW RESULT: PASS`. Final validation passed with 30 focused Milestone 3C.4b tests, 280 market-data tests, 589 full-suite tests, compileall, `git diff --check`, and a 50-name public `market_data` API. Milestone 3C.4b is implemented, independently reviewed, committed, and pushed. It remains structural declaration, validation, duplication control, and canonicalization only.
- Milestone 3C.4c exact identity and comparable-session coherence is implemented, independently reviewed with `REVIEW RESULT: PASS`, validated with 15 focused Milestone 3C.4c tests, 295 market-data tests, 604 full-suite tests, compileall, `git diff --check`, and a 54-name public `market_data` API, and committed and pushed. It adds exactly `MarketDataRelationshipIssueCode`, `MarketDataRelationshipGroupAssessment`, `MarketDataRelationshipAssessment`, and `assess_market_data_relationships`. It resolves the complete request before constructing results; retains exact request, timing-assessment, group, and binding objects; assesses exact resolved role types; and applies the four locked identity rules and the narrow comparable-session matrix. It contains no phase, scope, venue, methodology, activity-applicability, selection, transformation, pricing, or lineage behavior.
- Milestone 3C.4d quote phase, scope, and venue compatibility is implemented, independently reviewed with `REVIEW RESULT: PASS`, validated with 9 focused Milestone 3C.4d tests, 304 market-data tests, 613 full-suite tests, compileall, `git diff --check`, and an unchanged 54-name public `market_data` API, and committed and pushed in this operation. It adds no public name and appends exactly `MARKET_PHASE_MISMATCH`, `QUOTE_SCOPE_MISMATCH`, and `VENUE_MISMATCH` to the existing relationship issue enum. Compatibility applies only to the underlying/option quote snapshot: phase and scope use exact equality; normalized venue MIC is compared only when both quotes are venue-specific; and a scope mismatch suppresses venue comparison. Wrong resolved types still short-circuit all field access. Freshness eligibility, freshness artifacts, source-quality and provider concerns, analytics/activity/contract-reference coherence, selection, historical completeness, rates, dividends, transformations, pricing, evidence, and lineage remain excluded.
- Milestone 3C.4e analytics, activity, and contract-reference coherence is implemented, independently reviewed with `REVIEW RESULT: PASS`, validated with 7 focused Milestone 3C.4e tests, 311 market-data tests, 620 full-suite tests, compileall, `git diff --check`, and an unchanged 54-name public `market_data` API, and committed and pushed in this operation. It adds no public name and appends exactly `ANALYTICS_METHODOLOGY_MISMATCH`, `ACTIVITY_COHERENCE_MISMATCH`, and `CONTRACT_REFERENCE_APPLICABILITY_MISMATCH` to the relationship issue enum. It compares only same-contract IV/Greeks methodology tuples, enforces the locked volume/open-interest date/completeness matrix, and applies inclusive optional listing-date and last-trade-date bounds to each identity-matching observation. Wrong resolved types remain the sole issue and short-circuit every later check; identity mismatches suppress only locally misleading comparisons. Provider and source-lineage compatibility, freshness or timing recomputation, publication-time assumptions, calendar inference, selection, historical completeness, rates and dividends, pricing, transformations, evidence, and lineage remain excluded.
- Milestone 3C.4 relationship/group coherence is fully implemented across Milestones 3C.4a through 3C.4e. Broad Milestone 3 remains incomplete.
- Milestone 3C.5 deterministic cross-observation selection is implemented, independently reviewed, committed, and pushed in this operation. It adds exactly `MarketDataSelectionStatus`, `MarketDataSelectionReasonCode`, `MarketDataRelationshipSelection`, and `select_market_data_relationship_assessment`, bringing the public `market_data` API to 58 names. It validates and retains complete relationship-assessment candidates covering the complete comparable request/timing universe; comparability requires the same structural shape, target, correction regime, and freshness policy/context. Eligibility trusts the existing authoritative relationship- and timing-coherence properties. All aligned members contribute their `effective_observed_at` coordinate to a componentwise Pareto frontier, producing only selected, no-eligible-candidate, tied, or incomparable outcomes, with no scores, hidden lexical tiebreaks, or caller-order dependence. Exact candidate objects are retained. The initial independent review and targeted re-review failures identified only test-coverage gaps; all gaps were corrected without changing the source implementation or contract documentation, and the final targeted re-review passed. Final validation passed with 29 focused Milestone 3C.5 tests, 340 market-data tests, 649 full-suite tests, compileall, `git diff --check`, and a 58-name public `market_data` API.
- Milestone 3C.6 historical market-data series assembly and completeness is implemented, independently reviewed with all findings corrected, validated, committed, and pushed in this operation. The initial independent review found one MAJOR implementation validation-precedence defect and one MINOR focused-test adequacy defect; the implementation was refactored into global binding-element, selected-record-type, and integrity passes. The first targeted re-review confirmed the MAJOR defect was resolved but found incomplete late-phase mutation protection and a stale project-state transition; both were corrected. The next targeted re-review found that global phase-name deduplication could hide noncontiguous re-entry; the recorder was changed to collapse only contiguous repeats. The last targeted re-review returned `LAST TARGETED RE-REVIEW RESULT: PASS`. Final validation passed with 25 focused Milestone 3C.6 tests, 365 market-data tests, 674 full-suite tests, compileall, `git diff --check`, and exactly 64 public `market_data` names. The implementation supports only `UnderlyingDailyBarObservation` and `DAILY` frequency; accepts an explicit caller-supplied expected-session set and exact `SelectedFreshMarketDataBinding` objects; retains the exact request, bindings, and selected records; does not recompute correction selection or freshness; permits an empty observed binding set; derives missing, unexpected, duplicate, and incomplete sessions; requires one common correction/freshness proof regime for nonempty series; preserves duplicate-session records; assesses adjusted-close availability and adjustment-methodology consistency; uses deterministic canonical ordering; and exposes only complete or incomplete terminal status. It performs no calendar inference, interpolation, transformation, pricing, evidence construction, or lineage construction. It adds exactly `MarketDataHistoricalSeriesFrequency`, `MarketDataHistoricalSeriesStatus`, `MarketDataHistoricalSeriesReasonCode`, `MarketDataHistoricalSeriesRequest`, `MarketDataHistoricalSeriesAssessment`, and `assess_market_data_historical_series`.
- Broad Milestone 3C.7 was preflighted and found nonviable as one implementation unit, so it is decomposed into Milestones 3C.7a through 3C.7f.
- Milestone 3C.7a exact-structure liquidity transformation is implemented, independently reviewed, validated, and committed and pushed in this operation. The initial independent review returned `REVIEW RESULT: FAIL` with four MAJOR findings: incomplete retained-proof integrity, selected-record type-versus-integrity precedence, ambient Decimal-context dependence, and insufficient mutation-resistant focused coverage. The first targeted re-review returned `TARGETED RE-REVIEW RESULT: FAIL`: exact global selected-record type precedence was accepted, while exact proof enum/ID/sidecar validation, extreme Decimal behavior, and focused coverage still required correction. The second targeted re-review returned `SECOND TARGETED RE-REVIEW RESULT: FAIL`: proof exactness, Decimal exception normalization, and the requested malformed-proof tests were accepted, but one false-positive `MAX_EMAX` possible-carry rejection remained. After correction, the final targeted re-review returned `FINAL TARGETED RE-REVIEW RESULT: PASS`; all findings are resolved. The transformation consumes authoritative selected relationship proofs without recomputing correction, freshness, timing, relationship, selection, or historical completeness, and constructs an existing `StructureLiquidity` record with exact `CalculationLineage`. Its context-independent exact Decimal aggregation distinguishes exponent overflow at `decimal_aggregation` from finite-float rejection at `float_boundary`. The new module exports exactly `StructureLiquidityTransformationResult` and `transform_structure_liquidity`; `market_data.__all__` remains exactly 64 names and the package root remains unchanged. Final validation passed with 44 focused transformation tests, 365 market-data tests, 718 full-suite tests, compileall, and `git diff --check`.
- Milestone 3C.7a is committed and pushed at `bda1d2dbbbf68af5f4b6e3c937ac6de9bbbbbc05` (`Implement exact-structure liquidity transformation`).
- Milestone 3C.7b exact-structure cost transformation completed specification preflight with `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7B`, completed implementation with `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`, and completed independent review with `MVP-FOCUSED REVIEW RESULT: PASS`. The independent review found no findings and no remaining blocker. It consumes authoritative selected proofs without recomputing correction, freshness, timing, relationships, selection, or historical completeness. Its exact reviewed proof shape is three groups per leg. It constructs the existing `StructureCosts` record and exact `CalculationLineage`; contract-reference records are authoritative lineage inputs, giving four lineage inputs for a one-leg structure and seven for a two-leg structure. Its economic contract includes option midpoint premium, one-way midpoint-to-ask entry spread cost, explicit caller-supplied commissions and fees, position-scaled Theta and Gamma, underlying bid/ask midpoint, and an explicit repeated-bet count. Final validation passed with 61 focused transformation tests, including all original 44 Milestone 3C.7a liquidity tests; 365 market-data tests; 735 full-suite tests; compileall; both import orders; exact API, result-field, and signature checks; and `git diff --check`. `market_data_transformations.__all__` contains exactly `StructureLiquidityTransformationResult`, `transform_structure_liquidity`, `StructureCostsTransformationResult`, and `transform_structure_costs`; `market_data.__all__` remains exactly 64 names; and the package root remains unchanged. Milestone 3C.7b is implemented, independently reviewed, validated, and ready to commit and push. This operation commits and pushes Milestone 3C.7b.
- Milestone 3C.7b is committed and pushed at `ae0cf3bf32a41532cf67988c9fc6c2fd5c78b0bf` (`Implement exact-structure cost transformation`).
- Milestone 3C.7c historical underlying-return and realized-volatility transformation completed specification preflight with `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7C` and initially returned `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`. The initial independent review returned `MVP-FOCUSED REVIEW RESULT: FAIL`: the original calculation implementation, historical-assessment boundary, lineage, API, documentation, and economic/statistical formulas passed, but the review found exactly two MAJOR focused-test adequacy findings—`RAW_CLOSE` lacked symmetric protection when materially different adjusted prices were populated, and direct `HistoricalRealizedVolatility` construction guards lacked a compact rejection matrix. The first attempted test-only correction stopped before editing when the required matrix exposed one narrow source exception-taxonomy defect: `ADJUSTED_CLOSE` with `adjustment_methodology=None` raised `TypeError`, while the approved contract requires `ValueError`. The narrow source correction changed only basis/methodology validation order; the symmetric raw-basis adversarial test and direct-artifact rejection matrix were added. The final targeted independent re-review returned `TARGETED RE-REVIEW RESULT: PASS`, with no findings and no remaining blocker. Final validation passed with 75 focused transformation tests, all original 73 pre-correction focused tests, all 61 pre-3C.7c transformation regressions, 365 market-data tests, 749 full-suite tests, compileall, `git diff --check`, exact API, enum, artifact-field, wrapper-field, and signature checks, both import orders, and unchanged package-root exports. `market_data_transformations.__all__` contains exactly `StructureLiquidityTransformationResult`, `transform_structure_liquidity`, `StructureCostsTransformationResult`, `transform_structure_costs`, `HistoricalReturnPriceBasis`, `HistoricalRealizedVolatility`, `HistoricalRealizedVolatilityTransformationResult`, and `transform_historical_realized_volatility`; `market_data.__all__` remains exactly 64 names. `VolatilityEnvironment` remains unmodified and is not constructed by 3C.7c. The bounded `HistoricalRealizedVolatility` artifact and exact `CalculationLineage` retain an explicit raw or adjusted close basis without fallback or mixing, the complete accepted historical window, precision-34 Decimal natural-log returns, sample variance, explicit caller-supplied annualization sessions, and one lineage input per consumed selected daily bar; incomplete sessions, incomplete normalization, and partial sources are rejected. Milestone 3C.7c is implemented, independently reviewed, corrected, targeted re-reviewed, validated, and ready to commit and push; this operation commits and pushes it.
- Milestone 3C.7c is committed and pushed at `6be4e849c27efe75dce23cb163a97bd9932a975b` (`Implement historical realized volatility transformation`).
- Milestone 3C.7d volatility-environment construction completed specification preflight with `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7D`; one-unit 3C.7d was accepted and initially returned `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`. The initial MVP-focused review returned `MVP-FOCUSED REVIEW RESULT: FAIL` with exactly two MAJOR findings. First, multiple compatible call/put pairs could remain at the same selected strike, differentiated by multiplier, currency, deliverable, or another economic identity field; canonical ordering silently selected one instead of rejecting unresolved ambiguity. Second, focused tests did not protect Decimal percentile comparison from premature binary-float conversion. The ordinary ambiguity reproduction used strike 100, a multiplier-50 pair with ATM IV `0.10`, and a multiplier-100 pair with ATM IV `0.90`. ATM selection now identifies minimum distance, applies lower-strike equal-distance resolution, filters every remaining pair at the selected strike, requires exactly one final compatible pair, and raises `ValueError` when ambiguity remains. Canonical order, multiplier, currency, deliverable, record IDs, IV, premiums, liquidity, and caller order are never ATM economic tiebreakers. The Decimal precision-collapse reproduction uses current ATM IV `0.30000000000000002` and historical ATM IV `0.30000000000000003`; both convert to the same binary float, while the correct Decimal-first percentile is `0.0`. Percentile ranking continues to compare original Decimal ATM IV values before the final precision-34 division and float conversion. Focused regressions protect both unresolved same-strike ambiguity and Decimal values collapsing to one binary float. The final targeted independent re-review returned `TARGETED RE-REVIEW RESULT: PASS`, with no findings and no remaining blocker; both original MAJOR findings are closed. It confirmed that the source correction changes only the final ATM-pair cardinality rule, while ordinary nearest-pair selection, lower-strike tie behavior, caller-order invariance, current term structure, historical ATM calculation, percentile, median, realized matching, proof validation, lineage, and canonical parameters remain unchanged. Final validation passed with 89 focused transformation tests, all original 87 pre-correction focused tests, all 75 pre-3C.7d transformation regressions, 365 market-data tests, 763 full-suite tests, compileall, `git diff --check`, exact public API, wrapper-field, and signature checks, both import orders, unchanged package-root exports, and unchanged `VolatilityEnvironment` and `TermVolatilityPoint`. The exact transformation API is `StructureLiquidityTransformationResult`, `transform_structure_liquidity`, `StructureCostsTransformationResult`, `transform_structure_costs`, `HistoricalReturnPriceBasis`, `HistoricalRealizedVolatility`, `HistoricalRealizedVolatilityTransformationResult`, `transform_historical_realized_volatility`, `VolatilityEnvironmentTransformationResult`, and `transform_volatility_environment`; `market_data_transformations.__all__` has exactly 10 names, `market_data.__all__` has exactly 64 names, and the package root is unchanged. The frozen methodology requires caller-declared complete candidate universes, paired same-strike call/put ATM IV, nearest strike to the underlying bid/ask midpoint, lower-strike resolution for equal-distance strikes, rejection of unresolved same-strike compatible-pair ambiguity, a current calendar-day term structure, an explicit exact reference tenor, caller-declared historical observation dates, historical exact-tenor paired ATM IVs, inclusive empirical percentile, odd/even historical median, strict realized endpoint and calendar-span matching, flattened 3C.7c normalized lineage inputs, complete 3C.7c calculated-dependency disclosure, and Decimal-first calculations with final float boundaries. Milestone 3C.7d is implemented, independently reviewed, corrected, targeted re-reviewed, validated, and ready to commit and push; this operation commits and pushes it.
- Milestone 3C.7d is committed and pushed at `4c9de0bf32edd16df6a80c62e662382efebf38f8` (`Implement volatility environment transformation`).
- Milestone 3C.7e tail-relative pricing and skew transformation completed specification preflight with `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7E`. The one-unit tuple architecture is selected: `TailPricingTransformationResult` contains ordered existing `TailPricingSlice` records and one lineage. The combined `tail_candidate_universes_complete` declaration covers current nearest signed-delta selection and historical paired-ATM plus signed-delta selection. The methodology uses nearest observed signed delta with no interpolation, requires distinct same-side 10/25 contracts and strict selected absolute-delta ordering, strictly decodes the reviewed 3C.7d canonical parameters for exact current ATM Decimals, consumes an exact historical `D × T` relationship matrix under a caller-declared EOD methodology, uses downside 25-delta skew for the singular inclusive percentile, and performs a deterministic exact-overlap prior/direct lineage union. Milestone 3C.7e is implemented locally. `market_data_transformations.__all__` now has exactly 12 names; `market_data.__all__` remains exactly 64 names. Initial local validation passed with 101 focused transformation tests, 365 market-data tests, 775 full-suite tests, compileall, API/import checks, and `git diff --check`, after which the implementation entered its first MVP-focused independent review. Milestone 3C.7f remains unimplemented and responsible for pricing and scenarios; broad Milestone 3 remains incomplete.
- Milestone 3C.7e initially returned `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`. The first MVP-focused independent review returned `MVP-FOCUSED REVIEW RESULT: FAIL` with exactly one BLOCKER: the strict 3C.7d decoder checked canonical structure and dynamic consistency but did not validate frozen methodology semantics, so a canonically encoded dependency with `atm_candidate_universe.declared_complete=False` was accepted. Economically, a partial ATM candidate universe could therefore supply the wrong ATM IV, skew, and percentile while being represented as reviewed 3C.7d evidence. The narrow correction adds exact validation of the nested ATM candidate-universe declaration and every trusted fixed 3C.7d methodology declaration before ATM consumption. A canonical, byte-valid semantic-forgery regression rebuilds an otherwise internally consistent lineage and protects fixed-value and exact-type mutations. Post-correction validation passes with 102 focused transformation tests, all original 101 focused tests, all 89 pre-3C.7e regressions, 365 market-data tests, 776 full-suite tests, compileall, API/import checks, and `git diff --check`. Milestone 3C.7e remains uncommitted and unpushed; one targeted independent re-review is the next gate. Milestone 3C.7f remains unimplemented and broad Milestone 3 remains incomplete.
- The first targeted 3C.7e re-review returned `TARGETED RE-REVIEW RESULT: FAIL` with one remaining BLOCKER in the same dependency trust boundary. The fixed-declaration validator checked `iv_methodology` shape, canonical strings, and unit, but did not compare its four dynamic IV-methodology fields with the authoritative current and historical IV observations consumed by 3C.7e. Canonical dependencies forged as `model_name=Forged canonical model`, `model_version=forged-v9`, `rate_input_description=Forged curve`, or `dividend_input_description=Forged dividends` were accepted. This allowed a dependency to declare a different IV model or input methodology from the normalized IV observations used for ATM, skew, and percentile calculations, creating materially inconsistent lineage and crossing the reviewed methodology boundary. The complete decoded five-field 3C.7d IV-methodology tuple must now exactly equal the common authoritative IV tuple derived from every direct current and historical IV candidate before any ATM, skew, percentile, result, parameters, or lineage is constructed. Canonical byte-valid mutations of all four dynamic fields now reject. Final post-correction validation passes with 102 focused transformation tests, all original 102 focused tests, all original 101 pre-first-fix tests, all 89 pre-3C.7e regressions, 365 market-data tests, 776 full-suite tests, compileall, API/import checks, and `git diff --check`. Milestone 3C.7e remains uncommitted and unpushed; a final targeted independent re-review is the next gate. Milestone 3C.7f remains unimplemented and broad Milestone 3 remains incomplete.
- The final targeted 3C.7e re-review returned `FINAL TARGETED RE-REVIEW RESULT: FAIL`. Production behavior passed; only focused-test adequacy remained blocking. First, no test proved that the authoritative IV-methodology tuple covered both current and historical direct IV candidates. Second, no test proved that a forged dependency rejected before `TailPricingSlice` and new `CalculationLineage` construction. A production mutation deriving methodology only from the current partition or only from the historical partition could therefore leave the suite green, as could moving the dependency comparison after result or lineage construction. The test-only correction adds valid current-only and historical-only direct-methodology divergence cases, with each partition internally common, each IV/Greeks pair compatible, and every relationship selection selected and coherent. Constructor instrumentation additionally proves that neither `TailPricingSlice.__init__` nor new `CalculationLineage.__init__` is reached before dependency mismatch rejection. Production source and contract documentation remain byte-identical during this correction. Post-correction validation passes with 103 focused transformation tests, all original 102 focused tests, all original 101 pre-first-fix tests, all 89 pre-3C.7e regressions, 365 market-data tests, 777 full-suite tests, compileall, API/import checks, and `git diff --check`. Milestone 3C.7e remains uncommitted and unpushed; a final test-adequacy-only targeted re-review is the next gate. Milestone 3C.7f remains unimplemented and broad Milestone 3 remains incomplete.
- The final test-adequacy-only targeted re-review returned `FINAL TEST-ADEQUACY RE-REVIEW RESULT: PASS`, with no findings and no remaining blocker. It accepted the valid current-only and historical-only direct-methodology divergence fixtures and the `TailPricingSlice` and new `CalculationLineage` constructor instrumentation. All previous BLOCKER findings and test-adequacy gaps are closed, including the accepted mutation risks of deriving authoritative methodology from only the current partition, deriving it from only the historical partition, or performing the dependency comparison after `TailPricingSlice` or new `CalculationLineage` construction.
- The final reviewed 3C.7e architecture has exact public result `TailPricingTransformationResult` with fields `records` and `lineage`, and exact public function `transform_tail_pricing`. The result retains an ordered `Tuple[TailPricingSlice, ...]` and one `CalculationLineage`, requires at least two expirations, and canonically orders records by `days_to_expiration` and then `expiration`. Its frozen methodology requires a combined tail-candidate-universe completeness declaration: current candidates contain nearest-observed signed 10-delta and 25-delta candidates; historical candidates contain paired nearest-strike ATM candidates plus nearest-observed signed 10-delta and 25-delta candidates. Deltas are signed call-positive and put-negative. Selection is nearest observed signed delta with no delta, strike, or expiration interpolation; equal-distance ambiguity rejects; the same economic contract cannot serve both same-side targets; and `abs(selected 10-delta) < abs(selected 25-delta)` is strict. The transformation strictly decodes the 3C.7d canonical dependency and requires exact dependency-to-authoritative IV-methodology correspondence, consumes the historical dates × current tenors relationship matrix under caller-declared historical EOD observations and an explicit methodology, requires exact historical calendar-tenor matching and historical paired call/put ATM methodology, uses downside 25-delta skew for the singular skew percentile, computes the inclusive empirical percentile Decimal-first, and deterministically unions prior 3C.7d lineage inputs with direct 3C.7e inputs. `market_data_transformations.__all__` has exactly 12 names, `market_data.__all__` has exactly 64 names, and package-root exports are unchanged.
- Final 3C.7e validation passes with 103 focused transformation tests, all original 102 pre-final-test-correction focused tests, all original 101 pre-first-fix focused tests, all 89 pre-3C.7e transformation tests, 365 market-data tests, 777 full-suite tests, compileall, `git diff --check`, exact public API checks, exact wrapper-field and function-signature checks, and both import orders. `TailPricingSlice`, `VolatilityEnvironment`, and `TermVolatilityPoint` fields remain unchanged. Focused mutation protection proves that current-only and historical-only methodology divergences reject; all four canonical dependency dynamic-IV-methodology forgeries reject; dependency unit forgery rejects; `atm_candidate_universe.declared_complete=False` rejects; representative frozen-rule semantic forgeries reject; representative exact-type forgeries raise `TypeError`; and dependency mismatch rejects before either `TailPricingSlice` or new `CalculationLineage` construction. The unchanged ordinary 30-day output is ATM `0.30`, put-25 `0.36`, call-25 `0.28`, put-10 `0.42`, call-10 `0.26`, downside skew `0.06`, upside skew `-0.02`, downside curvature `0.06`, upside curvature `-0.02`, and skew percentile `2/3`; the unchanged ordinary 60-day output is ATM `0.40`, put-25 `0.46`, call-25 `0.38`, put-10 `0.52`, call-10 `0.36`, the same skews and curvatures, and skew percentile `2/3`. Ordinary lineage contains 202 unique normalized inputs; ordinary canonical parameters retain the exact 20-key schema and the literal golden remains byte-identical. The implementation consumes reviewed proof and lineage without calling any upstream proof function, recomputing correction, freshness, timing, relationships, or selection, or calling `transform_volatility_environment`.
- Milestone 3C.7e is implemented, independently reviewed, corrected, targeted re-reviewed, test-adequacy corrected, finally re-reviewed, validated, and ready to commit and push. This operation commits and pushes Milestone 3C.7e. Milestone 3C.7f remains unimplemented and broad Milestone 3 remains incomplete.
- Broad Milestone 3C.7f preflight returned
  `PREFLIGHT RESULT: DECOMPOSE 3C.7F BEFORE IMPLEMENTATION`. It is decomposed
  into 3C.7f1, the authoritative non-expiration scenario-pricing calculation
  contract, and 3C.7f2, `ScenarioResult` construction, expiration intrinsic
  payoff, reviewed `StructureCosts` and `TailPricing` dependencies, exit costs,
  bounded-loss handling, and downstream lineage.
- The 3C.7f1 contract preflight returned
  `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7F1`. The selected architecture has
  four immutable public calculated-evidence records, accepts
  `provider_calculated` evidence only, uses direct authoritative producer
  construction, and adds no public assembler or internal pricing engine. It
  supports non-expiration scenarios only and validates exact Decimal shocks,
  leg scaling, aggregate sums, canonical parameters, normalized-evidence
  disclosure, and shared lineage.
- Milestone 3C.7f1 is implemented locally and remains uncommitted and unpushed.
  The transformation API has exactly 16 names, `market_data.__all__` remains
  exactly 64 names, package-root exports remain unchanged, and no public
  function was added. Local validation passes with 114 focused transformation
  tests (all 103 prior tests plus 11 new tests), 365 market-data tests, 788
  full-suite tests, compileall, exact API/import/root/field checks, and
  `git diff --check`.
- The 3C.7f1 provider trust boundary validates classification, producer/model
  identity, request ID, payload-hash format, chronology, methodology,
  arithmetic, normalized evidence, lineage, parameters, and flags. It cannot
  prove that a deliberately self-consistent fraudulent provider declaration is
  truthful without the retained provider payload or a provider signature.
  No network verification, payload retrieval, authentication, or signature
  verification is attempted. Milestone 3C.7f2 remains unimplemented and broad
  Milestone 3 remains incomplete.
- The first 3C.7f1 independent review returned
  `MVP-FOCUSED REVIEW RESULT: FAIL` with exactly one MAJOR finding. The
  production implementation passed inspection and adversarial probes, but
  focused tests did not protect several frozen realistic invariants. Missing
  protections covered near-strike substitution, leg-IV evidence substitution,
  quantity scaling, missing and extra lineage inputs, source-ID mismatch,
  current-session IV mismatch, rate-date mismatch, dividend coverage and zero
  semantics, duplicate scenario identity, aggregate gross-value mismatch,
  unsupported exercise/settlement pairs, Decimal-context preservation on an
  ordinary failure, and the `transform_volatility_environment` scope sentinel.
  A future regression could accept the wrong option contract or IV evidence,
  mis-scale a position, accept incomplete or inconsistent provenance, misapply
  rate/dividend/style methodology, or cross the frozen scope boundary while
  the focused suite remained green.
- The test-adequacy-only correction adds four compact public-construction
  protections: one evidence/lineage mutation matrix, one methodology/batch
  matrix, one quantity-two scaling test, and one ordinary-failure Decimal
  context test. The existing scope sentinel now also blocks
  `transform_volatility_environment` and entry-cost, exit-cost, and P&L paths.
  All sixteen requested mutation classes are protected. Validation passes with
  118 focused transformation tests, an independent exclusion run of all 114
  original focused tests, 365 market-data tests, 792 full-suite tests,
  compileall, and `git diff --check`.
- No production defect was found. No production file or contract-document file
  was changed by the correction. Milestone 3C.7f1 remains uncommitted and
  unpushed; Milestone 3C.7f2 remains unimplemented and broad Milestone 3
  remains incomplete.
- The initial 3C.7f1 implementation returned
  `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`. Its frozen
  architecture has exactly four immutable public calculated-evidence records:
  `ScenarioPricingMethodology`, `ScenarioPricingLegCalculation`,
  `NonExpirationScenarioPricingCalculation`, and
  `ScenarioPricingCalculationResult`. The result fields are exactly `records`
  and `lineage`: an ordered
  `Tuple[NonExpirationScenarioPricingCalculation, ...]` and one shared
  `CalculationLineage`. `provider_calculated` is the only source
  classification. The authoritative provider constructs final evidence
  directly; there is no public assembler, internal pricing engine, or public
  pricing function, and 3C.7f1 does not calculate option values. It accepts
  `immediate`, `days_forward`, and `holding_horizon` scenarios and rejects
  `expiration`. `market_data_transformations.__all__` has exactly 16 names,
  `market_data.__all__` has exactly 64, package-root exports are unchanged,
  and no public function was added.
- The frozen economic scope is one long call, one long put, or one exact long
  straddle: one or two positive-quantity long legs with positive multipliers,
  one shared underlying, and one shared expiration. Short options, spreads,
  multiple expirations, and exotic options are excluded. Leg-to-contract
  correspondence requires exact underlying symbol, option type, expiration,
  `Decimal(str(OptionLeg.strike))`, and multiplier equality while preserving
  listing MIC, security type, currency, and deliverable from the exact
  `OptionContractKey`. Every leg uses one exact current-session IV evidence
  item in `annualized_decimal_ratio`; ATM or tail-wing substitution is
  prohibited unless that exact selected contract is the structure leg.
  Shocked IV is base IV times `1 + Decimal(str(scenario.iv_change))`. Base
  underlying is the disclosed bid/ask midpoint, and shocked underlying is base
  underlying times `1 + Decimal(str(scenario.underlying_move))`. After ratio
  conversion there is no binary-float arithmetic; local arithmetic uses
  precision 34 and `ROUND_HALF_EVEN` while preserving the caller Decimal
  context.
- `ScenarioPricingMethodology` retains provider classification, producer and
  model names and versions, request ID, payload SHA-256, producer time,
  supported exercise/settlement pairs, settlement treatment, provider-managed
  rate and dividend methodology, volatility-surface/skew/term/interpolation
  treatments, remaining-time and position-scaling rules, numerical boundary,
  and limitations. Fixed values are `provider_calculated`, USD,
  `expiration_minus_valuation_date_calendar_days`, and
  `per_underlying_unit_value_times_quantity_times_contract_multiplier`.
  Unsupported style/settlement pairs reject; the rate effective date equals
  `as_of_date`; dividend coverage includes `as_of_date` through shared
  expiration; missing dividends never imply zero; and explicit zero dividends
  require the exact reserved source and treatment declarations.
- Exact per-leg scaling is per-underlying-unit option value times leg quantity
  times contract multiplier. Estimated gross position value is the sum of
  total leg values. Scenario identity is valuation time, days forward,
  `Decimal(str(underlying_move))`, and `Decimal(str(iv_change))`. Canonical
  caller order is valuation date, valuation-time rank (`immediate`,
  `days_forward`, `holding_horizon`), days forward, underlying-move Decimal,
  and IV-change Decimal; noncanonical order rejects rather than being silently
  reordered.
- Exact normalized input scope is one underlying quote plus one IV and one
  contract-reference record per structure leg: three inputs for one-leg
  structures and five for long straddles. Direct option-quote and Greeks inputs
  are not supported in v0.1. Provider-internal rate, dividend, surface,
  calibration, quote, and Greeks data are disclosed through request ID,
  payload hash, typed methodology, and limitations rather than fabricated
  normalized records. Evidence and lineage correspond exactly on `record_id`,
  `normalized_at`, and `source_ids`; missing or extra inputs, source-ID
  mismatches, and current-session IV mismatches reject. Lineage identity is
  `nonexpiration_scenario_pricing`,
  `authoritative-provider-option-scenario-pricing-evidence`, `v0.1`, with
  every input normalized no later than producer calculation and producer
  calculation no later than lineage calculation.
- Canonical parameters use only `canonicalize_lineage_parameters`, tagged
  Decimals, no JSON floats, and an exact byte-canonical 23-key schema:
  `output_architecture`, `supported_structure_scope`, `producer_identity`,
  `producer_provenance`, `pricing_methodology`, `structure_identity`,
  `leg_correspondence`, `scenario_definitions`, `scenario_ordering`,
  `valuation_date_rules`, `underlying_shock_rule`, `iv_shock_rule`,
  `base_underlying_evidence`, `leg_iv_evidence`,
  `contract_reference_evidence`, `rate_methodology`, `dividend_methodology`,
  `exercise_and_settlement_support`, `remaining_time_rule`,
  `position_scaling_rule`, `calculation_values`, `float_conversion_rule`, and
  `limitations`. Duplicate keys, nonfinite constants, unknown or noncanonical
  tags, and missing or extra keys reject. `ANNUALIZED` and
  `ASSUMPTION_APPLIED` are always required. `ADJUSTED_INPUT_USED`,
  `CORRECTION_SELECTED`, `COMPOSITE_INPUT_USED`, and `INTERPOLATED` are
  conditional; `INTERPOLATED` arises only from disclosed rate or volatility
  interpolation, never scenario shocks. `DECIMAL_TO_FLOAT_CONVERTED` and
  `INCOMPLETE_INPUT_USED` are prohibited.
- The accepted MVP trust limitation is explicit: 3C.7f1 validates internal
  coherence, provider/model identity, request ID, payload-hash format,
  chronology, normalized evidence, canonical parameters, arithmetic, and
  lineage, but without the retained provider payload or a provider signature
  it cannot disprove a deliberately self-consistent fraudulent declaration.
  This disclosed limitation is not an unresolved blocker.
- The final focused-test correction protects canonical near-strike, IV-value,
  cross-leg IV-record, quantity-two, missing/extra/source-mismatched lineage,
  current-session IV, rate/dividend applicability, zero-dividend semantics,
  duplicate-scenario, straddle aggregate, unsupported style/settlement, and
  ordinary-failure Decimal-context fixtures, plus the expanded scope sentinel
  including `transform_volatility_environment`. The final targeted review
  returned `TARGETED RE-REVIEW RESULT: PASS`, with no findings and no remaining
  blocker. The single MAJOR test-adequacy gap is closed; production source and
  contract documentation remained byte-identical.
- Final validation passed: 118 focused transformation tests, all original 114
  focused tests independently, 365 market-data tests, 792 full-suite tests,
  compileall, and `git diff --check`. The exact 23-key literal golden, exact
  16-name API, exact four frozen field tuples, 64-name market-data API, both
  import orders, package-root exclusions, protected files, and all sixteen
  mutation protections passed. Ordinary gross values remain call `250.00`,
  `300.00`, `200.00`; put `250.00`, `300.00`, `200.00`; and straddle `600.00`,
  `700.00`, `500.00`, with straddle base IVs `0.20` and `0.30`. No internal
  pricing engine, `ScenarioResult` construction, expiration payoff, upstream
  transformation call, costs, P&L, or 3C.7f2 behavior exists.
- Milestone 3C.7f1 is implemented, independently reviewed, test-adequacy
  corrected, targeted re-reviewed, validated, committed, and pushed at
  `9d938465993306d61e5e0e6105f917f27d076614`
  (`Implement scenario pricing evidence contract`). Milestone 3C.7f2 remains
  unimplemented and broad Milestone 3 remains incomplete.
- The Milestone 3C.7f2 specification preflight returned
  `PREFLIGHT RESULT: NOT READY TO IMPLEMENT 3C.7F2`. Its accepted blocker was
  that a modified but valid `StructureCosts` record could be paired with
  untouched reviewed v0.1 lineage: changing quoted midpoint from `120.0` to
  `1120.0` changed the derived total entry cost from `141.25` to `1141.25`,
  while direct `StructureCostsTransformationResult` construction still
  accepted the pair.
- The bounded Milestone 3C.7b correction preflight returned
  `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7B DOWNSTREAM-VERIFIABILITY
  CORRECTION`. The selected architecture strengthens the existing wrapper and
  transformation parameters with no public API additions and no upstream proof
  replay. Methodology identity is now `structure_costs`,
  `exact-structure-costs`, `v0.2`; canonical parameters have exactly 20
  top-level keys; and the wrapper intrinsically verifies public record,
  structure identity, exact and stable calculation values, normalized
  evidence, lineage references, methodology, repeated bets, quality flags,
  and chronology.
- The selected Architecture A strengthens the existing
  `StructureCostsTransformationResult` wrapper and
  `transform_structure_costs` canonical parameters; it adds no public
  verifier, adapter, result class, generic calculated-artifact framework,
  producer bypass, or construction bypass. Direct wrapper validation does not
  invoke the producer, replay correction, freshness, snapshot timing,
  relationship assessment or selection, invoke a later transformation,
  construct `ScenarioResult`, or construct 3C.7f2 lineage.
- The exact correction identity is calculation type `structure_costs`,
  methodology ID `exact-structure-costs`, and methodology version `v0.2`.
  Version v0.2 is required because its exact canonical schema is incompatible
  with the prior 17-key v0.1 schema; no committed downstream transformation
  depended on v0.1 and no persisted-artifact migration requirement existed.
  Two incompatible exact canonical contracts do not share one methodology
  identity, and direct v0.1 dependencies intentionally reject.
- The original 17 top-level parameter keys remain, and exactly
  `calculation_values`, `normalized_evidence`, and `structure_identity` were
  added. The exact 20-key schema is `calculation_values`,
  `commission_and_fee_scope`, `commissions_and_fees_usd`, `gamma_input_unit`,
  `gamma_position_rule`, `greeks_methodology`, `leg_correspondence`,
  `normalized_evidence`, `position_value_unit`, `premium_input_unit`,
  `premium_midpoint_rule`, `repeated_bet_count`, `spread_cost_rule`,
  `spread_cost_scope`, `structure_identity`, `theta_day_basis`,
  `theta_input_unit`, `theta_position_rule`, `underlying_price_rule`, and
  `underlying_price_unit`. The private decoder rejects duplicate keys, JSON
  floats, nonfinite constants, unknown or noncanonical tags, wrong containers,
  missing or extra keys, and non-byte-canonical representations;
  `canonicalize_lineage_parameters` remains the only serializer.
- `structure_identity` has exactly `structure_type`, `underlying`,
  `assumed_portfolio_value_repr`, `expected_holding_days`, and `legs`; every
  leg has exactly `underlying`, `option_type`, `strike_float_repr`,
  `expiration`, `quantity`, and `contract_multiplier`. Public structure order
  is retained without silent reordering. Public `OptionStructure`,
  `structure_identity`, `leg_correspondence`, and normalized evidence
  correspond one-to-one on symbol, complete `UnderlyingKey`, option type,
  expiration, `Decimal(str(OptionLeg.strike))`, multiplier, quantity,
  currency, listing MIC, security type, and deliverable, with no missing,
  extra, duplicated, or reordered leg.
- `calculation_values` retains exact tagged Decimals for quoted midpoint,
  spread cost, commissions and fees, Theta, Gamma, underlying price, total
  entry cost, maximum loss, and cumulative repeated-bet cost. Its stable
  representation retains exact public `repr` strings for those nine direct or
  derived public values. Tagged Decimals preserve economic calculations;
  stable repr strings preserve the actual public binary-float boundary. Direct
  fields require `float(exact Decimal) == public float` and exact public repr.
  Total entry cost is independently checked using normal left-to-right public
  float addition. The reviewed exact `0.300` and stable
  `0.30000000000000004` case is valid and protected.
- Exact arithmetic remains total bid and ask as premium times quantity times
  multiplier; midpoint and one-way spread as their exact half-sum and
  half-difference; position Theta and Gamma as scaled sums; underlying price
  as the bid/ask midpoint; total entry as midpoint plus spread plus fees;
  maximum loss as total entry; and cumulative repeated-bet cost as total entry
  times the exact repeated-bet count. Public and canonical repeated-bet counts,
  exact cumulative cost, and stable cumulative repr must all correspond.
- `normalized_evidence` has exactly `underlying_quote`, `option_quotes`,
  `option_greeks`, and `contract_references`. Every item retains exact
  `record_id`, UTC `normalized_at`, sorted unique `source_ids`, and
  `propagated_quality_flags`, without complete normalized payloads or source
  payload bodies. One-leg results have exactly four inputs and straddles seven:
  one underlying quote, then one option quote, Greeks observation, and
  contract-reference record per public structure leg. Public as-of date equals
  all consumed observation sessions and every session precedes expiration.
- Normalized evidence corresponds exactly to each
  `CalculationInputReference` on record ID, normalization time, and source IDs.
  Missing or extra inputs, duplicate record IDs, normalization-time mismatch,
  and source-ID mismatch reject. Every normalized time is no later than
  lineage calculation time, while contract listing, last-trade, observation,
  and expiration chronology remains valid.
- The six-field Greeks methodology is `model_name`, `model_version`,
  `rate_input_description`, `dividend_input_description`, `theta_day_basis`,
  and `unit_convention`. Every leg uses one exact tuple, and canonical
  methodology generates the existing public disclosure string exactly.
  Public-only, canonical-only, single-leg evidence, and cross-leg methodology
  divergences reject.
- `DECIMAL_TO_FLOAT_CONVERTED` and `ASSUMPTION_APPLIED` are always required.
  `INTERPOLATED`, `CORRECTION_SELECTED`, and `COMPOSITE_INPUT_USED` are present
  if and only if normalized evidence discloses them. `ANNUALIZED`,
  `ADJUSTED_INPUT_USED`, and `INCOMPLETE_INPUT_USED` are prohibited, enum
  declaration order remains unchanged, and incomplete or partial selected
  evidence rejects before final result construction.
- Intrinsic wrapper validation covers exact public types, exact v0.2 identity,
  strict canonical syntax and schema, fixed rules and units, structure and
  as-of correspondence, leg/evidence correspondence, deterministic arithmetic,
  exact Decimal/public-float/stable-repr correspondence, Greeks methodology,
  repeated bets, exact lineage inputs, flags, and chronology. It detects
  public-record-only, canonical-parameter-only, normalized-evidence-value-only,
  lineage-reference-only, methodology, repeated-bet, flag, and chronology
  forgeries. It does not establish cryptographic authenticity; without
  signatures or immutable retained payloads, a deliberately self-consistent
  fabrication of record, parameters, evidence, source references, and lineage
  may remain possible. This accepted non-cryptographic MVP limitation is not a
  remaining blocker.
- The reviewed decisive direct-wrapper probe now raises `ValueError` when the
  valid ordinary record's midpoint is changed from `120.0` to `1120.0`, moving
  its derived total from `141.25` to `1141.25`, while its original v0.2 lineage
  remains untouched. Independent valid record-only changes also reject for
  quoted midpoint, spread cost, commissions and fees, Theta, Gamma, underlying
  price, Greeks methodology, repeated-bet count, structure, and as-of date.
- Ordinary one-leg stable values remain midpoint `120.0`, spread `20.0`, fees
  `1.25`, Theta `-10.0`, Gamma `2.0`, underlying `100.0`, and total `141.25`;
  exact values are `120.000`, `20.000`, `1.25`, `-10.000`, `2.000`,
  `100.000`, and `141.250`. Ordinary straddle stable values remain midpoint
  `350.0`, spread `50.0`, fees `1.25`, Theta `-25.0`, Gamma `5.0`, underlying
  `100.0`, and total `401.25`; exact values are `350.000`, `50.000`, `1.25`,
  `-25.000`, `5.000`, `100.000`, and `401.250`.
- Final validation passes with 128 focused transformation tests, 365
  market-data tests, 802 full-suite tests, compileall, and `git diff --check`.
  All pre-correction functional scenarios remain covered under required v0.2
  expectations. Three literal base-source assumptions were intentionally
  replaced because they asserted the obsolete v0.1 golden schema, obsolete
  v0.1 canonical ordering, and acceptance of partial or incomplete cost
  evidence; these are frozen-contract changes, not regressions. Precision,
  rounding, traps, flags, `Emin`, `Emax`, capitals, and clamp remain unchanged
  after successful transformation and direct construction and after record-,
  parameter-, evidence-, and lineage-only ordinary failures.
- The exact public boundaries remain two result fields (`record`, `lineage`),
  the unchanged `transform_structure_costs` signature, exactly 16
  transformation exports, exactly 64 market-data exports, unchanged package
  root, no new public names, and unchanged stable-domain files. A valid exact
  v0.2 dependency now proves structure, as-of date, exact and stable
  underlying-price basis, midpoint, spread, fees, total entry, maximum loss,
  Theta, Gamma, methodology, repeated bets, normalized evidence, lineage input
  set, flags, and chronology. Downstream 3C.7f2 therefore no longer needs the
  original relationship selection, selected/fresh bindings, complete
  normalized records, producer invocation, or upstream proof replay.
- The independent correction review returned
  `MVP-FOCUSED REVIEW RESULT: PASS`: findings none and remaining correction
  blocker none. It confirmed v0.2 identity and intentional v0.1 rejection, the
  exact 20-key schema, record/parameter/evidence/lineage binding, strict
  Decimal/stable-float boundary, ordinary arithmetic, flags, chronology,
  Decimal-context isolation, scope boundaries, focused-test adequacy, and the
  3C.7f2 downstream guarantee. The correction is implemented, independently
  reviewed, validated, and ready to commit and push. This operation commits
  and pushes the 3C.7b downstream-verifiability correction. Milestone 3C.7f2
  remains unimplemented, broad 3C.7f remains incomplete, and broad Milestone 3
  remains incomplete.
- Milestone 3C.7f1 is committed and pushed at
  `9d938465993306d61e5e0e6105f917f27d076614`. The StructureCosts v0.2
  downstream-verifiability correction is committed and pushed at
  `1f8df729857d9ba6496da5440d72087a39ff592c`
  (`Strengthen structure costs evidence verification`).
- The prior 3C.7f2 StructureCosts blocker is closed. The rerun specification
  preflight returned `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7F2`.
- Milestone 3C.7f2 is implemented locally under the frozen hybrid
  architecture: reviewed 3C.7f1 gross values are authoritative for
  non-expiration scenarios without repricing; expiration uses internal exact
  terminal intrinsic payoff; all results use reviewed StructureCosts v0.2,
  contextual TailPricing v0.1, actual leg-level IV evidence, explicit ordered
  exit costs, bounded-loss validation, and one shared downstream lineage.
- The transformation API adds exactly
  `ScenarioValuationTransformationResult` and
  `transform_scenario_valuation`, for exactly 18 transformation exports.
  The wrapper fields are exactly `records` and `lineage`;
  `market_data.__all__` remains exactly 64 and package-root exports remain
  unchanged.
- Exact dependencies are `structure_costs` / `exact-structure-costs` / `v0.2`,
  `tail_pricing` /
  `nearest-observed-delta-wing-tail-relative-pricing` / `v0.1`, and
  `nonexpiration_scenario_pricing` /
  `authoritative-provider-option-scenario-pricing-evidence` / `v0.1`.
  All calculation IDs are mutually distinct and all dependencies must precede
  the new calculation.
- Declared scenarios are a nonempty canonical exact tuple with at least one
  non-expiration scenario. `scenario_grid_complete=False` explicitly
  discloses a subset; `True` requires the exact frozen 7-by-4 Cartesian product
  for every valuation-time/days-forward group. Exit costs are an ordered exact
  tuple using the same scenario objects and finite nonnegative Decimals.
- Every public ScenarioResult methodology uses the exact canonical 15-key v0.1
  schema and every downstream lineage uses the exact canonical 25-key schema.
  The lineage identity is `scenario_valuation`,
  `hybrid-authoritative-nonexpiration-terminal-intrinsic-after-costs`, `v0.1`;
  ordinary no-overlap input counts are 209 for one leg and 214 for a straddle.
- The first 3C.7f2 independent review returned
  `MVP-FOCUSED REVIEW RESULT: FAIL` with exactly two BLOCKER findings, one
  MAJOR finding, and zero MINOR findings: exactly `2 BLOCKER`, `1 MAJOR`,
  `0 MINOR`.
- BLOCKER 1: direct `ScenarioValuationTransformationResult` construction
  validated only part of `calculation_values` and did not bind public base IVs,
  shocked IVs, complete dependency identities, or complete nested schemas to
  lineage. Canonical, internally inconsistent artifacts were accepted when
  public base IV `0.20` was changed to `0.91` with untouched lineage, when the
  StructureCosts downstream disclosure was changed from v0.2 to v0.1, and when
  the ScenarioPricing downstream methodology identity was forged.
- BLOCKER 2: an exact TailPricing matching candidate compared contract identity
  and IV but did not compare IV record ID or contract-reference record ID with
  the ScenarioPricing leg evidence. A matching Tail candidate with IV evidence
  `ve-current-1-call-iv` and contract-reference evidence
  `ve-current-1-call-reference` accepted ScenarioPricing evidence IDs
  `scenario-iv-0` and `scenario-reference-0`.
- MAJOR: the focused tests did not directly protect the two blocker paths.
- The bounded correction completes intrinsic validation of every public
  ScenarioResult field, complete 20-key calculation-value entries, all three
  dependency disclosures and identities, and the complete nested 15-key record
  methodology. It also requires exact IV-record and contract-reference IDs
  whenever a structure leg matches a current TailPricing candidate by contract
  and IV.
- Direct adversarial regressions now protect public-IV and cross-leg forgeries;
  dependency identity, nested schema, fixed-semantic, stable-representation,
  scenario-identity, valuation-source, and methodology mutations; both Tail
  evidence-ID mismatches; constructor precedence; and complete Decimal-context
  preservation on the corrected failure paths.
- Post-correction validation passes 144 focused transformation tests, all
  original 139 focused tests in an independently assembled suite, 365
  market-data tests, and 818 full-suite tests. Compileall, `git diff --check`,
  exact API/fields/signature, both import orders, package-root, four-file scope,
  protected-file, unstaged, and no-untracked-file checks pass.
- The first targeted 3C.7f2 re-review returned
  `TARGETED RE-REVIEW RESULT: FAIL` with exactly `1 BLOCKER`, `1 MAJOR`,
  `0 MINOR`.
- Remaining BLOCKER: the ScenarioValuation intrinsic verifier did not
  completely validate nested TailPricing v0.1 `parameters_json` schemas.
  Canonical missing or extra fields in selected-put/selected-call records and
  historical observations were accepted with untouched public ScenarioResult
  records.
- MAJOR: focused tests did not mutate nested content inside retained
  TailPricing `parameters_json`, allowing the incomplete validation to remain
  green.
- The final bounded correction reuses one authoritative private TailPricing
  schema validator for the producer dependency and downstream intrinsic
  decoder. It validates the complete current, selected-option, candidate,
  historical, paired-ATM, embedded dependency, exact-container, canonical-tag,
  ordering, selection-correspondence, and metric tree. Direct byte-canonical
  mutations protect every reviewed nested boundary and complete Decimal-context
  preservation.
- Final post-correction validation passes 147 focused transformation tests,
  the previous 144-test and 139-test focused checkpoints in independently
  assembled suites, 365 market-data tests, and 821 full-suite tests.
  Compileall, `git diff --check`, exact API/fields/signature, both import
  orders, package-root, four-file scope, protected-file, unstaged, and
  no-untracked-file checks pass.
- The final targeted 3C.7f2 re-review returned
  `FINAL TARGETED RE-REVIEW RESULT: PASS`: findings none and remaining 3C.7f2
  blocker none. One broad independent review and its bounded targeted
  re-reviews are complete.
- The final frozen architecture consumes reviewed 3C.7f1 authoritative
  provider-calculated gross values unchanged for every non-expiration scenario
  and calculates exact terminal intrinsic payoff internally for expiration.
  Every scenario consumes intrinsically revalidated StructureCosts v0.2,
  contextual TailPricing v0.1, actual 3C.7f1 per-leg IV evidence, and one
  explicit per-scenario exit cost; constructs one ordered existing
  `ScenarioResult`; validates liquidation, after-cost P&L, return, and bounded
  loss; and contributes to one shared `CalculationLineage`. It adds no internal
  non-expiration pricing engine, provider API, probability or expected-return
  forecast, screening, recommendation, candidate-state derivation, sizing,
  execution, `CandidateResearchRecord`, short, spread, multiple-expiration, or
  exotic behavior.
- The exact API additions are `ScenarioValuationTransformationResult` and
  `transform_scenario_valuation`. Wrapper fields are exactly `records` and
  `lineage`; there is no public exit-cost-assumption record. The signature is
  `transform_scenario_valuation(calculation_id: object,
  structure_costs_result: object, tail_pricing_result: object,
  scenario_pricing_result: object, scenarios: object,
  scenario_grid_complete: object, exit_cost_assumptions: object,
  exit_cost_methodology: object, calculated_at: object) ->
  ScenarioValuationTransformationResult`. Transformation exports are exactly
  18, `market_data` exports remain exactly 64, and package-root exports are
  unchanged.
- The downstream identity is exactly `scenario_valuation`,
  `hybrid-authoritative-nonexpiration-terminal-intrinsic-after-costs`, `v0.1`.
  Its three calculated dependencies are `structure_costs` /
  `exact-structure-costs` / `v0.2`, `tail_pricing` /
  `nearest-observed-delta-wing-tail-relative-pricing` / `v0.1`, and
  `nonexpiration_scenario_pricing` /
  `authoritative-provider-option-scenario-pricing-evidence` / `v0.1`.
  StructureCosts is completely revalidated for exact underlying, midpoint,
  spread, fees, total entry, maximum loss, stable representations, structure,
  evidence, inputs, flags, and chronology; its reviewed stable underlying and
  total-entry floats are reused directly. TailPricing is contextual evidence
  only and never substitutes ATM, wing, skew, or curvature for actual leg IV.
  ScenarioPricing gross values, shocks, remaining time, methodology, and
  evidence are consumed without repricing.
- All dependencies correspond exactly on structure, underlying, as-of date,
  expiration, leg order, economic contracts, multipliers, exact base
  underlying, and actual leg IV evidence. The new and three dependency
  calculation IDs are mutually distinct, and no dependency calculation time
  may follow the new calculation.
- `scenarios` is an exact nonempty canonical tuple of unique exact `Scenario`
  items with at least one non-expiration item. Identity is valuation time,
  days forward, Decimal-string underlying move, and Decimal-string IV change.
  Supported times are immediate, days forward, holding horizon, and optional
  expiration. `scenario_grid_complete` is an exact bool: false declares the
  supplied subset; true requires the exact 7-by-4 product of moves `-0.20`,
  `-0.10`, `-0.05`, `0`, `0.05`, `0.10`, `0.20` and relative IV changes
  `-0.20`, `0`, `0.20`, `0.50` in every time/days group. Valuation dates are
  the as-of date, calendar-days-forward date, expected-holding-days date, or
  expiration. Ordering is valuation date, time rank, days forward, move
  Decimal, then IV-change Decimal; caller order is validated, never reordered.
- Actual per-leg IVs come only from reviewed 3C.7f1 evidence and correspond on
  public leg order, economic contract, IV, IV record ID, and contract-reference
  ID. `LegVolatilityInput` follows public structure order. Shocked IV is exact
  base IV times one plus the Decimal-string relative shock. Expiration results
  retain the same base-IV audit inputs even though payoff is IV-independent.
- The ScenarioPricing record set equals the declared non-expiration set with
  exactly one record per scenario and exact date, underlying, shock, leg-IV,
  and evidence correspondence; its gross position value is consumed unchanged
  and no repricing function or provider adapter is called. Expiration uses
  isolated precision-34, `ROUND_HALF_EVEN` Decimal arithmetic, exact shocked
  underlying, and the exact sum of long-call
  `max(shocked-strike, 0) * quantity * multiplier` and long-put
  `max(strike-shocked, 0) * quantity * multiplier` payoffs. Expiration date is
  the valuation date, remaining days are zero, provider expiration values are
  prohibited, and IV does not affect terminal payoff.
- Exit costs are exactly `Tuple[Tuple[Scenario, Decimal], ...]`, one finite
  nonnegative Decimal for each identical declared scenario object in identical
  order and cardinality, with no missing, extra, duplicate, or reordered item.
  One shared canonical nonempty methodology applies. Zero is valid only when
  explicitly supplied; costs are not inferred from entry costs, spreads,
  liquidity, or TailPricing.
- Exactly one `ScenarioResult` is constructed per scenario from the reviewed
  common structure/date, exact scenario object and date rule, stable
  StructureCosts underlying and entry-cost floats, actual ordered leg IVs,
  provider or intrinsic gross value, explicit finite exit-cost float, and
  canonical methodology. The exact 15-key methodology retains both active and
  inactive branches, uses valuation source
  `authoritative_provider_nonexpiration` or
  `terminal_intrinsic_expiration`, contains no JSON float, is serialized only
  by `canonicalize_lineage_parameters`, and exactly matches both its
  calculation-value item and top-level disclosure. Both reviewed methodology
  byte goldens remain unchanged and pass.
- Downstream parameters retain exactly the reviewed 25 keys and golden.
  Duplicate keys, JSON floats, nonfinite constants, unknown or noncanonical
  tags, wrong containers/items, missing or extra top-level or nested keys, and
  non-byte-canonical documents reject. Direct
  `ScenarioValuationTransformationResult(records, lineage)` construction uses
  the producer's complete intrinsic verifier and binds every record's
  structure, date, scenario, underlying, base and shocked IVs, gross, entry,
  exit, methodology, liquidation, P&L, return, and bounded-loss state to
  canonical calculation values. A public base IV changed from `0.20` to `0.91`
  with untouched `0.20` lineage rejects, as does cross-leg `0.20`/`0.30`
  substitution.
- All three retained dependency disclosures are checked for complete identity,
  exact nested schema, complete retained `parameters_json`, calculation time,
  flags, and selected decoded values. Canonical StructureCosts v0.2-to-v0.1,
  TailPricing v0.1-to-v9.9, and forged ScenarioPricing-methodology disclosures
  reject.
- Complete retained TailPricing parameters mean the full frozen v0.1 tree:
  current observations have exactly 18 keys; selected put/call and current
  candidate records each have exactly 13 keys; historical observations have
  exactly 18 keys; historical selected options use the complete shared schema;
  and nested containers enforce exact items, cardinality, keys, canonical tags,
  uniqueness, correspondence, and order. Missing or extra selected-put,
  selected-call, candidate, historical, or historical-selected-option fields;
  tuple-for-map or map-for-collection substitutions; reordered current
  candidates or history; Decimal-to-string; and date-to-datetime mutations all
  reject. Complete unmodified parameters validate. An exact current Tail
  candidate agrees with ScenarioPricing on economic contract, IV, IV record
  ID, and contract-reference ID; either ID mismatch rejects and all-four-match
  succeeds. Arbitrary structure legs need not be selected Tail candidates.
- Normalized lineage references are flattened only from the three calculated
  dependencies. Equal record ID, normalized time, and source IDs deduplicate;
  conflicting overlaps reject. Ordinary counts are 209 for one leg and 214 for
  a straddle regardless of scenario count. Dependencies, scenarios,
  assumptions, calculations, and results are not fabricated normalized inputs.
  Required flags are `DECIMAL_TO_FLOAT_CONVERTED`, `ANNUALIZED`, and
  `ASSUMPTION_APPLIED` in enum order; `INTERPOLATED`,
  `ADJUSTED_INPUT_USED`, `CORRECTION_SELECTED`, and `COMPOSITE_INPUT_USED`
  propagate if and only if present; intrinsic expiration alone does not add
  interpolation; `INCOMPLETE_INPUT_USED` is prohibited.
- Decimal remains authoritative through scenario identities, shocks, provider
  values, expiration payoff, base/shocked IVs, exit assumptions, and canonical
  values. Conversion occurs only for public leg IV, gross value, and exit cost;
  reviewed StructureCosts stable floats are reused. Precision, rounding, traps,
  flags, Emin, Emax, capitals, and clamp are preserved after success and every
  reviewed failure.
- Net liquidation is `max(gross - exit cost, 0.0)`; after-cost P&L is net
  liquidation less entry cost; return is P&L divided by entry cost. Every
  result has `loss_is_within_entry_cost` true and P&L no worse than negative
  entry cost; exact maximum loss equals exact total entry cost; liquidation
  floors at zero when exit cost exceeds gross value.
- Review chronology is preserved: the broad review returned
  `MVP-FOCUSED REVIEW RESULT: FAIL` with exactly `2 BLOCKER`, `1 MAJOR`,
  `0 MINOR` for incomplete direct binding, missing Tail/Scenario evidence-ID
  comparison, and missing adversarial protection. The first targeted re-review
  returned `TARGETED RE-REVIEW RESULT: FAIL` with exactly `1 BLOCKER`,
  `1 MAJOR`, `0 MINOR` for incomplete nested TailPricing validation and tests.
  Every accepted finding was corrected, and the final targeted re-review
  passed.
- Final validation passes 147 focused transformation tests, independently
  assembled previous checkpoints of 144 and 139 tests, 365 market-data tests,
  and 821 full-suite tests; compileall and `git diff --check` pass. Ordinary
  long-call and long-put gross values are each `250.0`, `300.0`, `200.0`,
  `1000.0`; straddle values are `600.0`, `700.0`, `500.0`, `1000.0`. Both
  15-key methodology goldens and the exact 25-key lineage golden remain
  unchanged and pass.
- The 3C.7f2 trust boundary validates internal consistency of reviewed
  dependencies, scenarios, assumptions, arithmetic, public records, canonical
  parameters, lineage, flags, and chronology. It does not establish
  cryptographic authenticity; without signatures or immutable retained
  provider payloads, a deliberately self-consistent fabrication of every
  dependency artifact may remain possible. This accepted non-cryptographic MVP
  limitation is not a blocker.
- Milestone 3C.7f2 is implemented, corrected for all accepted review findings,
  independently reviewed, final-targeted-re-review passed, validated, and ready
  to commit and push. This operation commits and pushes Milestone 3C.7f2.
  Milestone 3C.7f2 is complete, broad Milestone 3C.7f is complete, and because
  3C.7f2 was the final explicitly defined Milestone 3 gate, broad Milestone 3
  is complete.
- Milestone 3 is complete at
  `86aee1dfa13cae0c865d8f24aa08754934abd540`
  (`Implement hybrid scenario valuation transformation`).
- The post-Milestone-3 product-direction alignment is complete. It accepts two
  entry modes; Chinese-only active reporting with a simplified beginner
  overview; exact expiration 1x/2x/5x/10x threshold evidence; explicit
  risk-budget boundaries; first-report monetization, reassessment, and exit
  conditions without monitoring or automatic trading; mature Skill reuse with
  explicit native-output and adapter risk; and eligibility plus layered
  selection instead of arbitrary candidate caps.
- The mode-based Strike and Delta discovery-generation policy is accepted and
  documented in ADR-007, product direction, and the MVP specification. It
  preserves distinct extreme-tail, event-directional, and bidirectional
  expansion modes; direct-entry flexibility; mode-appropriate future
  scenarios; and explicit cheapness and risk-budget boundaries. This is a
  completed documentation decision, not an implemented generation component.
- The revised Milestone 4 formal preflight initially returned `BLOCKED`
  because public numeric representation and evidence architecture were
  unresolved.
- The accepted exact-rational artifact, dependency, mathematics, lineage,
  ordering, and exclusion clarification was frozen and committed before
  BUILD.
- BUILD implemented the frozen contract. Broad independent review found three
  MAJOR issues: Boolean/integer canonical substitutions, forged nested public
  objects, and an arbitrary Decimal exponent cap.
- All three findings were accepted and corrected. Targeted re-review passed
  with all three resolved and no remaining MAJOR finding.
- Final validation passes with 174 focused transformation tests, 365
  market-data tests, 848 full-suite tests, non-writing compilation, both
  import orders, API checks, and `git diff --check`.
- Milestone 4 is complete and remains preserved at the last implementation
  checkpoint.
- The formal risk-budget and affordability preflight initially returned
  `BLOCKED`. A documentation-only clarification then froze the standalone
  v0.1 contract.
- Milestone 5 BUILD implemented the frozen contract in the seven-name
  `convexity_hunter.risk_assessment` API without changing package-root,
  transformation, or `market_data` exports.
- Broad independent review returned 0 BLOCKER, 2 MAJOR, and 2 MINOR findings.
  ChatGPT accepted strict normalized-input reconstruction, independent
  canonical golden serialization, and removal of Milestone 4 private-validator
  coupling. It rejected proposed raw propagation of resource-exhaustion
  exceptions because controlled `ValueError` behavior remained part of the
  accepted BUILD boundary.
- All three accepted findings were corrected. Targeted re-review resolved 3/3
  accepted findings with no remaining MAJOR or MINOR finding.
- Final Milestone 5 validation passes with 32 focused risk-assessment tests,
  174 focused transformation tests, 365 market-data tests, 880 full-suite
  tests, non-writing compilation, both import orders, API checks, and
  `git diff --check`.
- Milestone 5 is complete at the last implementation checkpoint. The
  risk-assessment API contains
  exactly seven names; transformation and `market_data` exports remain 25 and
  64.

## Current task

The Deterministic Direct-Entry Reviewed-Research Service is implemented and
independently reviewed under
[`direct-entry-reviewed-research-service-contract.md`](direct-entry-reviewed-research-service-contract.md).
The direct module has exactly two public names and zero package-root exports.
Its implementation and focused tests are
`src/convexity_hunter/direct_entry_reviewed_research_service.py` and
`tests/test_direct_entry_reviewed_research_service.py`.

The service delegates in exact order to direct-entry verification, candidate
assembly, and the offline single-structure service, retaining all delegated
results and propagating failures unchanged. It adds no provider, retrieval,
eligibility, selection, transformation, calculation, lineage, screening,
plan, or report authority. Independent review returned
`IMPLEMENTATION REVIEW RESULT: PASS`; validation passed 11 focused tests and
1,059 full-suite tests.

## Previous implementation checkpoint

- Commit: current finalization commit with subject
  `Implement prospective position management plan`
- Parent: `a41b35df797c0720410c548841c5bb456b20f2ce`
- Validation: 60 position-management tests, 366 market-data tests, 181
  transformation tests, 50 candidate-assembly tests, 32 risk-assessment
  tests, 998 full-suite tests, API/import probes, canonical goldens, no-call
  probes, and `git diff --check` passed
- Status: Milestones 1–5, 6A, 6B, and the standalone unnumbered
  Position-Management Plan Contract are complete; final targeted re-review
  passed with no remaining findings
- Risk-assessment public API: 7 names
- Transformation-module public API: 25 names
- Public `market_data` API: 64 names

### Preserved checkpoint chronology

The entries below preserve earlier checkpoint wording and interim states. They
do not override the current Milestone 6A completion checkpoint above.

- Milestone 3C.1 semantic observation identity complete
- Milestone 3C.2 per-record selected/fresh binding complete
- Milestone 3C.3 binding-set temporal coherence complete
- Milestone 3C.4a auditable binding references complete
- Milestone 3C.4b explicit relationship/group request representation complete
- Milestone 3C.4b independently reviewed
- Milestone 3C.4c exact identity and comparable-session coherence complete
- Milestone 3C.4c independently reviewed
- Milestone 3C.4d quote phase, scope, and venue compatibility complete
- Milestone 3C.4d independently reviewed
- Milestone 3C.4e analytics, activity, and contract-reference coherence complete
- Milestone 3C.4e independently reviewed
- Milestone 3C.5 deterministic cross-observation selection complete
- Milestone 3C.5 independently reviewed after correction of test-only coverage gaps
- Final targeted re-review: `FINAL TARGETED RE-REVIEW RESULT: PASS`
- Milestone 3C.5 commit `7f59c38e238a265f18b529fe10fe3eaebca94ea4`
- Milestone 3C.6 remains the last committed checkpoint
- Initial Milestone 3C.6 independent review: `REVIEW RESULT: FAIL`
- Milestone 3C.6 review findings: one implementation precedence defect and one focused-test adequacy defect
- Milestone 3C.6 selected-record/type-versus-integrity precedence corrected locally
- Initial Milestone 3C.6 MINOR test-adequacy defect substantially corrected
- First targeted re-review: `TARGETED RE-REVIEW RESULT: FAIL`
- First targeted re-review findings: one remaining MINOR late-phase mutation-protection gap and one stale project-state task transition
- Milestone 3C.6 constructor/function and complete late-phase precedence coverage strengthened
- Milestone 3C.6 project-state task transition corrected
- Second targeted re-review: `FINAL TARGETED RE-REVIEW RESULT: FAIL`
- Second targeted re-review accepted the source implementation and project-state transition
- Second targeted re-review finding: global phase-name deduplication hid noncontiguous phase re-entry
- Milestone 3C.6 phase recorder and explicit noncontiguous re-entry protection corrected locally
- Last targeted re-review: `LAST TARGETED RE-REVIEW RESULT: PASS`
- Milestone 3C.6 implemented, independently reviewed, validated, committed, and pushed in this operation
- Milestone 3C.6 final validation: 25 focused, 365 market-data, 674 full-suite
- Milestone 3C.6 public `market_data` API: 64 names
- Milestones 3C.1 through 3C.6 implemented
- Milestone 3C.4d validation: 9 focused, 304 market-data, 613 full-suite
- Milestone 3C.4d public `market_data` API: 54 names
- Milestone 3C.4e validation: 7 focused, 311 market-data, 620 full-suite
- Milestone 3C.4e public `market_data` API: 54 names
- Milestone 3C.4 fully implemented across 3C.4a through 3C.4e
- Broad Milestone 3C.7 decomposed into Milestones 3C.7a through 3C.7f
- Initial Milestone 3C.7a independent review: `REVIEW RESULT: FAIL`
- Initial Milestone 3C.7a findings: four MAJOR defects in retained-proof
  integrity, type/integrity precedence, ambient Decimal-context isolation, and
  mutation-resistant focused coverage
- First Milestone 3C.7a correction pass completed locally
- Milestone 3C.7a targeted re-review: `TARGETED RE-REVIEW RESULT: FAIL`
- Targeted re-review accepted global selected-record precedence and ordinary
  ambient Decimal-context isolation
- Targeted re-review findings: incomplete exact enum, retained-ID, and
  correction-sidecar validation; leaked `decimal.Overflow` at extreme
  exponents; and missing exact-type, exponent, and independent-permutation
  focused tests
- Second Milestone 3C.7a targeted re-review:
  `SECOND TARGETED RE-REVIEW RESULT: FAIL`
- Second targeted re-review accepted exact proof validation, global
  selected-record precedence, Decimal exception normalization, and the
  requested malformed-proof tests
- Second targeted re-review finding: a blanket possible-carry estimate falsely
  rejected representable multi-term sums at `decimal.MAX_EMAX`
- Milestone 3C.7a exponent preflight corrected to reserve possible carry only
  for coefficient precision and let trapped exact addition determine actual
  sum overflow
- Literal representable multi-term `decimal.MAX_EMAX`, actual coefficient-carry
  overflow, caller-context, and public float-boundary regression tests added
- Final Milestone 3C.7a targeted re-review:
  `FINAL TARGETED RE-REVIEW RESULT: PASS`
- All Milestone 3C.7a review findings resolved
- Milestone 3C.7a uses global selected-record typing before proof integrity,
  exact proof-sidecar, enum, and retained-ID validation, exponent-bounded exact
  local Decimal arithmetic, and a mutation-protected 21-phase sequence
- Milestone 3C.7a implemented and independently reviewed with 44 focused tests
- Milestone 3C.7a final validation: 44 focused, 365 market-data, 718 full-suite,
  compileall, and `git diff --check`
- Milestone 3C.7a public module API: exactly two names
- Milestone 3C.7a committed and pushed in this operation
- Milestone 3C.7b specification preflight:
  `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7B`
- Milestone 3C.7b implementation:
  `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`
- Milestone 3C.7b independent review:
  `MVP-FOCUSED REVIEW RESULT: PASS`
- Independent review found no findings and no remaining blocker
- Milestone 3C.7b implemented, independently reviewed, validated, and ready to
  commit and push
- Milestone 3C.7b validation: 61 focused transformation tests, 365 market-data
  tests, 735 full-suite tests, compileall, API/import checks, and
  `git diff --check`
- All original 44 Milestone 3C.7a focused tests remain passing
- Transformation-module public API: exactly four names
- Public `market_data` API: unchanged at exactly 64 names
- Milestone 3C.7b committed and pushed at
  `ae0cf3bf32a41532cf67988c9fc6c2fd5c78b0bf`
- Milestone 3C.7c preflight completed with no genuine blocker
- `VolatilityEnvironment` rejected as the direct 3C.7c output
- `HistoricalRealizedVolatility` selected as the bounded intermediate artifact
- Milestone 3C.7c initially returned
  `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`
- First 3C.7c independent review:
  `MVP-FOCUSED REVIEW RESULT: FAIL`
- First review found exactly two MAJOR test-adequacy gaps: missing symmetric
  raw-basis protection and incomplete direct-artifact rejection coverage
- First attempted test-only correction stopped before editing after exposing
  adjusted basis plus `adjustment_methodology=None` as `TypeError` instead of
  the contract-required `ValueError`
- Narrow source exception taxonomy and both test gaps corrected locally;
  contract documentation unchanged
- Final 3C.7c targeted independent re-review:
  `TARGETED RE-REVIEW RESULT: PASS`
- Targeted re-review found no findings and no remaining blocker
- Milestone 3C.7c implemented, independently reviewed, corrected, targeted
  re-reviewed, validated, and ready to commit and push
- Milestone 3C.7c validation: 75 focused transformation tests, 365 market-data
  tests, 749 full-suite tests, compileall, API/import checks, and
  `git diff --check`
- All original 73 pre-correction focused tests and all 61 pre-3C.7c
  transformation regressions remain passing
- Transformation-module public API: exactly eight names
- Public `market_data` API: unchanged at exactly 64 names
- Milestone 3C.7c committed and pushed at
  `6be4e849c27efe75dce23cb163a97bd9932a975b`
- Milestone 3C.7d specification preflight:
  `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7D`
- One-unit Milestone 3C.7d accepted and implemented locally
- Caller-declared complete paired-ATM candidate universes required
- Historical relationship selections and explicit sample dates selected
- Strict realized endpoint and calendar-span matching selected
- Reviewed 3C.7c lineage flattened and dependency disclosed
- Transformation-module public API: exactly ten names
- Initial 3C.7d independent review:
  `MVP-FOCUSED REVIEW RESULT: FAIL`
- Review findings: unresolved same-strike compatible-pair ambiguity and
  missing Decimal-before-float percentile regression protection
- Same-strike multiplier-50 versus multiplier-100 ambiguity now raises
  `ValueError` after distance and lower-strike resolution
- Decimal precision-collapse case `0.30000000000000002` versus
  `0.30000000000000003` now protects the exact `0.0` percentile
- Milestone 3C.7d post-correction validation: 89 focused transformation tests,
  365 market-data tests, 763 full-suite tests, compileall, API/import checks,
  and `git diff --check`
- Final targeted independent re-review:
  `TARGETED RE-REVIEW RESULT: PASS`
- Targeted re-review found no findings and no remaining blocker; both original
  MAJOR findings are closed
- Targeted re-review confirmed only the final ATM-pair cardinality rule changed
- Milestone 3C.7d is implemented, independently reviewed, corrected, targeted
  re-reviewed, validated, and ready to commit and push
- This operation commits and pushes Milestone 3C.7d
- Milestone 3C.7d committed and pushed at
  `4c9de0bf32edd16df6a80c62e662382efebf38f8`
- Milestone 3C.7e specification preflight:
  `PREFLIGHT RESULT: READY TO IMPLEMENT 3C.7E`
- Milestone 3C.7e one-unit ordered tuple architecture selected
- Combined tail-candidate completeness declaration selected
- Nearest observed signed-delta methodology and no interpolation selected
- Distinct same-side 10/25 contracts and strict selected-delta ordering required
- Strict 3C.7d canonical parameter decoding selected
- Historical `D × T` relationship matrix and caller-declared EOD methodology selected
- Downside 25-delta skew selected for the singular percentile
- Deterministic prior/direct lineage union selected
- Milestone 3C.7e implemented locally
- Transformation-module public API: exactly 12 names
- Public `market_data` API: unchanged at exactly 64 names
- Milestone 3C.7e local validation: 101 focused transformation tests,
  365 market-data tests, 775 full-suite tests, compileall, API/import checks,
  and `git diff --check`
- Initial implementation entered one MVP-focused independent review
- Initial 3C.7e implementation result:
  `IMPLEMENTATION RESULT: READY FOR MVP-FOCUSED INDEPENDENT REVIEW`
- First 3C.7e MVP-focused review:
  `MVP-FOCUSED REVIEW RESULT: FAIL`
- Review found exactly one BLOCKER: canonical structure and dynamic
  correspondence did not protect frozen 3C.7d methodology semantics
- Canonical `atm_candidate_universe.declared_complete=False` was accepted
- Economic impact: a partial ATM universe could produce a wrong ATM IV, skew,
  and percentile while represented as reviewed 3C.7d evidence
- Fixed nested ATM-universe and every trusted fixed 3C.7d declaration now
  require exact reviewed semantic values before ATM consumption
- Canonical byte-valid semantic forgery and compact value/type mutations added
- Post-correction validation: 102 focused transformation tests, all original
  101 focused tests, all 89 pre-3C.7e regressions, 365 market-data tests,
  776 full-suite tests, compileall, API/import checks, and `git diff --check`
- Milestone 3C.7e remains uncommitted and unpushed
- First targeted re-review:
  `TARGETED RE-REVIEW RESULT: FAIL`
- Remaining BLOCKER: the four dynamic dependency IV-methodology fields were
  not compared with authoritative current and historical IV observations
- Accepted canonical forgeries: `Forged canonical model`, `forged-v9`,
  `Forged curve`, and `Forged dividends`
- Complete decoded dependency IV tuple now exactly equals the common direct
  current/historical IV tuple before any ATM or derived output is consumed
- Canonical byte-valid mutations of all four dynamic fields now reject
- Final post-correction validation: 102 focused transformation tests, all
  original 102 focused tests, all original 101 pre-first-fix tests, all 89
  pre-3C.7e regressions, 365 market-data tests, 776 full-suite tests,
  compileall, API/import checks, and `git diff --check`
- Final targeted re-review:
  `FINAL TARGETED RE-REVIEW RESULT: FAIL`
- Production implementation passed; focused-test adequacy remained blocking
- Missing protection: no test covered both current and historical methodology
  partitions, and no test protected pre-result/pre-lineage rejection ordering
- Test-only correction adds valid current-only and historical-only divergence
  plus `TailPricingSlice` and `CalculationLineage` constructor instrumentation
- Production source and contract documentation remain unchanged by this fix
- Post-test-correction validation: 103 focused transformation tests, all
  original 102 focused tests, all original 101 pre-first-fix tests, all 89
  pre-3C.7e regressions, 365 market-data tests, 777 full-suite tests,
  compileall, API/import checks, and `git diff --check`
- Final test-adequacy-only targeted re-review:
  `FINAL TEST-ADEQUACY RE-REVIEW RESULT: PASS`
- Final test-adequacy re-review findings: none
- Final test-adequacy re-review remaining blocker: none
- All previous 3C.7e BLOCKER findings and test-adequacy gaps are closed
- Milestone 3C.7e implemented, independently reviewed, corrected, targeted
  re-reviewed, test-adequacy corrected, finally re-reviewed, validated, and
  ready to commit and push
- This operation commits and pushes Milestone 3C.7e
- Milestone 3C.7f remains unimplemented
- Broad Milestone 3 incomplete

## Next task

Any subsequent capability requires fresh repository grounding, formal
preflight, and a separately frozen contract before implementation.

## Current capability and roadmap

Convexity Hunter has largely completed the auditable numerical and evidence
foundation for researching one already-specified option structure. It has not
yet completed the active-discovery front end, real option-structure
generation, broader discovery/application-flow candidate production,
non-expiration pricing production, or the complete application flow. The
standalone position-management plan and its separate downstream Chinese
report integration are complete. Reviewed-artifact candidate assembly is
complete: 6A strengthens three existing wrappers and 6B assembles reviewed
artifacts into the existing `CandidateResearchRecord` plus a
provenance-retaining sidecar. Deterministic
exact-rational expiration 1x/2x/5x/10x
threshold evidence and reviewed standalone structure-affordability evidence
are implemented.

Status claims must distinguish an implemented capability, an implemented
record or contract, a transformation that requires caller orchestration,
synthetic-only integration, and work not yet implemented. A domain record is
not a complete application workflow.

The accepted post-Milestone-3 sequence is:

1. prior documentation alignment;
2. completed Milestone 4 — Deterministic Expiration Payoff-Threshold Evidence;
3. completed Milestone 5 — Standalone Structure Affordability Evidence;
4. completed Milestone 6A — Reviewed Artifact Verifiability;
5. completed Milestone 6B — Reviewed-Artifact Candidate Assembly;
6. completed standalone, unnumbered Position-Management Plan Contract;
7. completed separate, unnumbered Position-Management Plan Screening and
   Chinese-Report Integration;
8. completed deterministic offline single-structure service contract,
   implementation, focused tests, and independent review;
9. completed deterministic direct-entry exact-structure verification contract,
   implementation, focused tests, and independent review;
10. completed deterministic direct-entry reviewed-research service contract,
    implementation, focused tests, and independent review; and
11. Tiger local runtime boundary and bounded provider adapter work; and
12. subsequent pricing-reference, Skill, Event Intelligence, mapping,
    discovery, generation, and complete-flow work.

## Tiger provider decision and current work unit

Tiger OpenAPI is the accepted MVP primary market-data provider for a bounded
personal research universe. The feasibility spike verified authentication,
US-option quote permission, exact monthly contract identification, current
option-chain facts, option and underlying history, and historical dividends.
Known gaps remain explicit: historical option IV/Greeks, a 30–150 DTE USD term
curve, forward-dividend completeness, and some quote/analytics semantics.

The local Tiger runtime boundary is defined in
[`tiger-provider-contract.md`](tiger-provider-contract.md). It adds only
deterministic external configuration-path resolution and non-networking,
non-preempting SDK client initialization. It does not retrieve or normalize
market data. Credentials remain outside the repository and model context.

This work unit is implemented and independently reviewed. It adds exactly two
direct-module public functions under `convexity_hunter.providers.tiger`, zero
package-root or provider-package re-exports, a lazy optional
`tigeropen==3.7.0` extra, and defense-in-depth credential ignore rules. The
initial independent review found four accepted security/test findings covering
SDK import sanitization, pre-construction root logging, adjacent-token error
handling, and actual-SDK isolation coverage. All were corrected, and targeted
re-review passed. Final validation passed 26 focused tests, 1,085 full-suite
tests, compileall, `git diff --check`, and a local external-config smoke check
that returned a `QuoteClient` without a market request or permission grab.

The next separately contracted work unit is
[`tiger-option-contract-verification-contract.md`](tiger-option-contract-verification-contract.md).
It is limited to verifying one caller-specified exact option identity against
Tiger's explicit monthly expiration evidence and exact chain row, retaining the
provider identifier and provider-supplied multiplier in a provider-neutral
`OptionContractReference`. It does not scan, rank, substitute, generate, or
normalize quote/analytics fields. Contract status: frozen; implementation and
independent review pending.

## Deferred

- Tiger market-data retrieval and normalization beyond the completed local
  runtime boundary and the separately contracted exact-option verification
  work unit
- additional or fallback market-data providers unless a concrete Tiger blocker
  appears
- mature news, search, knowledge, and world-event Skill capability research
- Skill adapters and multi-Skill composition
- last30days-skill or similar narrative integrations
- Serenity Alpha investigation
- Event Intelligence and event-to-underlying mapping
- option-chain access, contract validation, and supported structure generation
- exact standard-monthly-option definition and deterministic Delta/ATM
  resolution contracts
- non-expiration scenario-pricing production
- broader discovery/application-flow candidate production beyond the active
  reviewed-artifact assembly contract
- future annual convexity-budget contract
- Chinese beginner-overview renderer changes
- LLM integration
- user interface
- automatic execution
- monitoring, alerts, notifications, scheduled tasks, and automated exits
- Markdown escaping before untrusted external narrative text is rendered
- global custom-policy registration or fingerprinting

Deferred does not mean rejected. These items remain outside the current milestone and may be reconsidered later.

## Open questions

- What bounded deterministic reconstruction should produce historical option
  IV from Tiger option/underlying bars plus explicit rate and dividend inputs?
- Should non-expiration pricing use an external provider, internal model, or both?
- What exact historical lookback should be used for IV percentile and skew percentile?
- How should liquidity thresholds vary by asset class?
- Which world-event and narrative Skills are sufficiently reliable and auditable?
- What are the exact standard-monthly and event-window contracts?
- What exact Delta convention, nearest-eligible-Delta and tie rules, expiration
  interaction, ATM reference, and mode-specific quote/liquidity rules should
  generation use?
- How should asset-class and event-specific extreme-tail stresses be
  calibrated?
- What contract should accept an optional caller-supplied annual convexity
  budget?
- What final record should hold portfolio value, single-loss and repeated-loss
  boundaries, and methodology?
- What exact Python API, annotations, validation, and exports should implement
  the clarified position-management plan?
- What is the final accepted event-to-underlying contract?
- How may incomplete direct-entry descriptions be resolved without inventing
  contracts?
