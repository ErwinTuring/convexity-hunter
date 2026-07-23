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
- Milestones 3C.7b through 3C.7f remain unimplemented. Return calculation, realized volatility, adjusted/raw price selection, rate/dividend relationship and economic use, other research transformations, and pricing remain later 3C.7 slices. Exchange-calendar inference and historical option surfaces remain future contracts. Broad Milestone 3 remains incomplete.

## Current task

Finalize, commit, and push Milestone 3C.7a.

## Last completed checkpoint

- Checkpoint: Milestone 3C.7a implemented, independently reviewed, and
  validated; final targeted re-review passed
- Base commit: `b2259a8859672da209c715bba83418dd428081fc`
  (`Implement historical market data series assessment`)
- Base checkpoint: Milestone 3C.4e complete at `6c7566167af503c260f8df67095810002dd12604`
- Milestone 3C.5 validation: 29 focused, 340 market-data, 649 full-suite
- Public `market_data` API: 64 names
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
- Milestones 3C.7b through 3C.7f unimplemented
- Broad Milestone 3 incomplete

## Next task

Perform a short specification preflight for Milestone 3C.7b exact-structure
cost transformation, using MVP-appropriate review scope.

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
