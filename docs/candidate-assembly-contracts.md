# Candidate-Assembly Contracts

This document is the canonical technical contract for Milestone 6. It freezes
the product and architecture decisions needed for later formal preflight and
implementation. The exact Milestone 6A calculation identities and canonical
parameter schemas are frozen in
[`market-data-contracts.md`](market-data-contracts.md#1324-milestone-6a-reviewed-artifact-verifiability-contract).
Milestone 6B public API, module layout, calculation identity, and canonical
parameter schema remain for its later formal preflight.

## 1. Milestone decomposition and gate

Milestone 6 is decomposed into these ordered work units:

1. **Milestone 6A — Reviewed Artifact Verifiability**; and
2. **Milestone 6B — Reviewed-Artifact Candidate Assembly**.

Milestone 6A is complete: it has been implemented, independently reviewed,
corrected for all accepted findings, and passed targeted re-review. The three
direct wrappers strengthened by 6A now satisfy the intrinsic-verifiability
prerequisite. Milestone 6B remains unimplemented and is unlocked only for its
fresh formal read-only preflight.

## 2. Direct reviewed-artifact boundary

The direct candidate-facing reviewed artifacts are exactly:

1. `VolatilityEnvironmentTransformationResult`;
2. `TailPricingTransformationResult`;
3. `StructureLiquidityTransformationResult`;
4. `StructureCostsTransformationResult`;
5. `ScenarioValuationTransformationResult`;
6. `ExpirationPayoffThresholdTransformationResult`; and
7. `StructureAffordabilityAssessmentResult`.

Historical realized volatility, provider scenario pricing, normalized
observations, correction selection, freshness, relationship assessment, and
other nested inputs remain indirect dependencies retained through those
direct wrappers. Candidate assembly does not duplicate them as separate
direct inputs.

Milestone 6A introduced no new public class or function, changed no producer
signature or public domain-record field, and preserves all current export
counts and ordering. Its exact v0.2 identities, retained-evidence schemas, and
private verification behavior are frozen in the linked market-data contract.
The formal 6B preflight remains responsible for 6B's exact public sidecar,
function signature, implementation-file list, calculation identity, and
canonical parameter schema.

## 3. State-specific artifact completeness

Candidate assembly receives a caller-supplied `CandidateState`. It validates
whether the supplied artifacts and disclosures are compatible with that state;
it does not derive or change the state.

### 3.1 `CandidateState.INVESTIGATE`

An `INVESTIGATE` candidate requires all seven direct reviewed artifacts. No
direct artifact lineage may contain
`CalculationQualityFlag.INCOMPLETE_INPUT_USED`.

The supplied `StructureAffordabilityAssessmentResult` must be conclusive: its
status is `AffordabilityStatus.AFFORDABLE` or
`AffordabilityStatus.NOT_AFFORDABLE`. `NOT_AFFORDABLE` does not automatically
change or reject the supplied candidate state. Candidate assembly validates
and retains the caller's state; it does not perform screening.

### 3.2 `CandidateState.WATCH` and `CandidateState.REJECT`

A `WATCH` or `REJECT` candidate may contain any subset of the seven direct
artifacts, including a complete set. If any direct artifact is absent or any
present direct artifact has incomplete-input quality, the resulting
`CandidateResearchRecord.missing_data` must be nonempty.

### 3.3 `CandidateState.DATA_INSUFFICIENT`

A `DATA_INSUFFICIENT` candidate may contain any subset of the direct artifacts.
Its `CandidateResearchRecord.missing_data` remains mandatory and nonempty. A
complete reviewed artifact may be retained when a different required fact is
unavailable.

### 3.4 Rules common to every state

Malformed or contradictory artifacts are errors. Absence or valid
incompleteness is not automatically a candidate-state decision. Candidate
assembly does not invoke screening.

## 4. Direct dependency closure

Presence of a dependent direct artifact requires presence of its matching
direct dependency:

- a supplied `TailPricingTransformationResult` requires the matching supplied
  `VolatilityEnvironmentTransformationResult`;
- a supplied `ScenarioValuationTransformationResult` requires matching
  supplied `VolatilityEnvironmentTransformationResult`,
  `TailPricingTransformationResult`, and
  `StructureCostsTransformationResult` values;
- a supplied `ExpirationPayoffThresholdTransformationResult` requires the
  matching supplied `StructureCostsTransformationResult`; and
- a supplied `StructureAffordabilityAssessmentResult` requires the matching
  supplied `StructureCostsTransformationResult`.

A dependent artifact is not acceptable merely because its lineage contains
an indirect nested disclosure while the corresponding direct candidate
artifact is omitted.

## 5. Exact shared-dependency identity

One assembled candidate uses one authoritative reviewed calculation for each
shared dependency. The assembly must require:

- the Tail Pricing artifact's retained Volatility Environment dependency to
  be the exact supplied Volatility Environment calculation;
- the Scenario Valuation artifact's retained Tail Pricing and Structure Costs
  dependencies to be the exact supplied calculations;
- the Expiration Payoff Threshold artifact's retained Structure Costs
  dependency to be the exact supplied costs calculation; and
- the Structure Affordability artifact's retained Structure Costs dependency
  to be the exact supplied costs calculation.

The sidecar described below retains each supplied direct wrapper unchanged.
For shared-dependency comparison, "exact supplied calculation" includes
complete equality of the relevant calculation ID, calculation type,
methodology ID and version, calculated time, canonical parameters, normalized
input references, quality flags, and public record or records.

An independently calculated but economically equivalent `StructureCosts`,
Volatility Environment, or Tail Pricing artifact cannot coexist as a
substitute for the authoritative supplied calculation in one assembled
candidate.

## 6. Milestone 6A — Reviewed Artifact Verifiability

Milestone 6A strengthens exactly these existing wrappers:

- `VolatilityEnvironmentTransformationResult`;
- `TailPricingTransformationResult`; and
- `StructureLiquidityTransformationResult`.

Their direct constructors now completely bind public output records to
retained lineage. The implemented correction architecture is:

- strengthen the existing wrappers rather than introduce replacements;
- make direct construction perform complete intrinsic record-to-lineage
  verification;
- make producer-created and directly reconstructed results use the same
  verifier;
- keep the verifier private;
- introduce no generic calculated-artifact framework;
- introduce no candidate-assembly-local duplicate verifier;
- perform no upstream market-data recomputation; and
- add no provider behavior.

The accepted implementation resolves the former schema and version blockers.
The exact identities are:

- `volatility_environment`, `paired-atm-volatility-environment`, `v0.2`;
- `tail_pricing`,
  `nearest-observed-delta-wing-tail-relative-pricing`, `v0.2`; and
- `structure_liquidity`, `exact-structure-liquidity`, `v0.2`.

Each v0.2 canonical parameter schema retains complete normalized evidence,
complete lineage references, exact public reconstruction values, and the
dependency disclosures required for intrinsic record-to-lineage verification.
Current producers emit v0.2 and strengthened direct constructors accept only
their exact v0.2 contract. Former v0.1 wrapper instances intentionally reject;
there is no migration function, legacy verifier, compatibility adapter,
dual-version constructor path, or persisted-artifact migration requirement.
The complete schemas, quality-flag derivation, downstream dependency behavior,
failure taxonomy, noncryptographic trust boundary, and exclusions are frozen
in
[`market-data-contracts.md`](market-data-contracts.md#1324-milestone-6a-reviewed-artifact-verifiability-contract).

Milestone 6A is complete. The next gate is
`PREFLIGHT｜Milestone 6B — Reviewed-Artifact Candidate Assembly`, a fresh
formal read-only preflight. All existing Milestone 6B aggregate, sidecar,
provenance, completeness, dependency-identity, chronology, quality, and
exclusion contracts below remain unchanged; this status update does not
pre-decide the exact 6B public API.

## 7. Milestone 6B aggregate architecture

Milestone 6B preserves the existing `CandidateResearchRecord` in `report.py`
as the compatibility domain aggregate used by current scanner and renderer
code. It does not move that record and does not change scanner or renderer
integration.

Milestone 6B introduces a narrow assembly result or sidecar that retains:

- the constructed existing `CandidateResearchRecord`;
- every exact supplied direct reviewed wrapper; and
- assembly-level deterministic provenance through `CalculationLineage`.

The Milestone 4 Expiration Payoff Threshold and Milestone 5 Structure
Affordability artifacts remain complete reviewed artifacts in the sidecar.
They are not converted to prose, flattened into `ClassifiedEvidence`, or
inserted into screening.

The exact public sidecar name, fields, producer signature, module exports, and
canonical schema remain decisions for the formal 6B preflight.

## 8. Assembly-level provenance

Milestone 6B uses an assembly-level `CalculationLineage` in addition to
retaining the complete direct wrappers.

### 8.1 Dependency disclosures and normalized inputs

The assembly lineage retains complete dependency disclosures for every
present direct artifact. Complete upstream wrappers or equivalent complete
dependency disclosures remain necessary; flattened normalized inputs alone
are insufficient provenance.

Its normalized inputs are the deterministic union of the present artifacts'
normalized input references. Inputs are deduplicated only when record ID,
normalized time, and the source-ID tuple are all identical. Any overlap that
shares an identity but conflicts in normalized time or source IDs rejects.

### 8.2 Identity and chronology

Assembly calculation time must not precede any retained dependency
calculation time or normalized-input time. The assembly calculation ID must
differ from every dependency calculation ID and every normalized-input record
ID.

### 8.3 Quality flags

The assembly lineage propagates every present upstream quality flag in
canonical `CalculationQualityFlag` enum order. It adds
`INCOMPLETE_INPUT_USED` when at least one direct artifact is absent and
retains that flag when any present dependency propagates it.

No quality flag is added merely because caller qualitative text, an
assumption-classified evidence item, or AI interpretation is present.

### 8.4 Caller qualitative parameters

Caller-supplied qualitative material belongs in canonical assembly parameters.
It is not fabricated as normalized market-data observations. This
clarification does not freeze the exact canonical parameter-key schema or
assembly calculation identity strings.

## 9. Qualitative-input ownership

The caller remains the explicit owner of:

- candidate ID;
- `CandidateState`;
- state rationale;
- hypothesis;
- `ClassifiedEvidence`;
- falsification conditions;
- missing-data descriptions;
- false-positive reasons;
- optional AI interpretation; and
- human-review questions.

Candidate assembly does not call an LLM, generate prose, infer
`EvidenceImpact`, convert numerical artifacts automatically into
`ClassifiedEvidence`, derive candidate state, or create screening reasons.
Reviewed artifacts remain the numerical authority. Qualitative evidence
remains explicitly classified caller material.

## 10. Legacy portfolio-value boundary

`OptionStructure.assumed_portfolio_value` remains provisional compatibility
metadata. Exact affordability arithmetic continues to use
`PortfolioValueAssumption`. The Milestone 5 requirement that an exact
portfolio-value assumption equal
`Decimal(str(OptionStructure.assumed_portfolio_value))` remains the
compatibility guard.

Candidate assembly introduces no second portfolio-value authority. Scanner
use of existing legacy portfolio-relative fields is unchanged because
screening integration is deferred. Milestone 6 adds no holdings, committed
exposure, annual budget, inverse sizing, or quantity calculation.

## 11. Explicit exclusions

Milestones 6A and 6B contain no:

- discovery or Event Intelligence;
- event-to-underlying mapping;
- option-chain access or contract resolution;
- structure generation or Strike or Delta selection;
- provider access or production scenario pricing;
- screening, screening reasons, or candidate-state derivation;
- renderer integration or report changes;
- position-management plan;
- services, sizing, ranking, or recommendation;
- monitoring, alerts, scheduled tasks, or execution;
- generic artifact registry; or
- generic transformation framework.

Broader discovery, application-flow candidate production, screening and
report integration, position management, and production services remain later
work.
