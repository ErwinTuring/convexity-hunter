# Risk-Assessment Contracts

This document is the canonical technical specification for the implemented
v0.1 standalone risk-budget and affordability evidence contract. The
implementation in `convexity_hunter.risk_assessment` passed broad independent
review, correction of all accepted findings, and targeted re-review.

## 1. Purpose and exclusions

The v0.1 work unit produces standalone, auditable affordability evidence for
one already-specified supported long option structure. It answers:

> Does the bounded maximum-loss scenario of this declared structure fit the
> caller's explicitly declared single-position and repeated-attempt risk
> boundaries?

It does not recommend a trade; derive, recommend, or optimize quantity;
calculate maximum affordable quantity; alter the structure; optimize a
portfolio; calculate expected return or probability; automatically reject a
candidate; modify screening, candidate assembly, or report rendering; create a
position-management plan; or access providers, services, holdings, monitoring,
or execution systems.

### 1.1 Fixed risk scopes

v0.1 uses two separate caller boundaries:

1. maximum loss fraction for one already-specified structure; and
2. maximum cumulative loss fraction for the dependency's declared equal
   repeated-attempt scenario.

Both boundaries are required for a conclusive affordability result. The
repeated scenario means equal repeated attempts represented by the reviewed
`repeated_bet_count`. It does not mean concurrent portfolio exposure, annual
trading frequency, an annual tail-protection budget, expected occurrence
count, or full portfolio holdings. Existing committed exposure and annual
convexity budgets are excluded.

No public risk-scope enum is required. The two fixed public fields and
canonical methodology declarations define the scopes.

### 1.2 Budget representation

v0.1 accepts fraction-based boundaries only and no absolute USD risk-budget
field. Both boundaries:

- use the existing public `ExactRational` type from
  `convexity_hunter.market_data_transformations`;
- require exact type `ExactRational`;
- are mathematically within inclusive range `[0, 1]`, including exact zero;
  and
- use no float or rounded `Decimal` conversion.

An exact zero boundary makes every positive applicable loss exceed that
boundary. Budget utilization, remaining budget, maximum affordable quantity,
and derived absolute budget amounts are not public v0.1 outputs.
`ExactRational` is neither moved nor redefined.

## 2. Sole computational dependency

The sole computational dependency is an exact, intrinsically revalidated
`StructureCostsTransformationResult` v0.2. The assessment consumes its
reviewed structure, as-of date, exact `maximum_loss_exact`, exact
`total_entry_cost_exact`, exact `repeated_bet_count`, exact repeated aggregate
cost disclosure, calculation identity and time, canonical parameters,
normalized input references, and quality flags.

Exact lineage data, not the public float properties of `StructureCosts`, is
the arithmetic authority. The assessment does not recompute structure cost or
read quotes directly. It does not depend on Milestone 4 expiration thresholds,
Scenario Valuation, Scenario Pricing, Tail Pricing, screening, candidate
records, reports, or providers.

## 3. Module and public API

The implementation belongs in the module
`convexity_hunter.risk_assessment`. Direct imports use that module. Its
`__all__` contains exactly these seven names in this order:

```text
PortfolioValueAssumption
RiskBudgetAssumptions
AffordabilityStatus
AffordabilityReasonCode
StructureAffordabilityEvidence
StructureAffordabilityAssessmentResult
assess_structure_affordability
```

The implementation does not change package-root exports,
`market_data.__all__` (64), or `market_data_transformations.__all__` (25).
Candidate assembly and all downstream integrations remain excluded.

## 4. Public records and enums

### 4.1 `PortfolioValueAssumption`

```python
@dataclass(frozen=True)
class PortfolioValueAssumption:
    amount: Decimal
    as_of_date: date
    methodology: str
```

`amount` requires exact type `Decimal` and must be finite and strictly
positive. `as_of_date` requires exact type `date`, not `datetime`.
`methodology` requires exact type `str`, is stripped, and must remain nonempty.
Currency is fixed to `USD` and is not a public field. The portfolio-value date
must equal the reviewed StructureCosts `as_of_date`.

### 4.2 `RiskBudgetAssumptions`

```python
@dataclass(frozen=True)
class RiskBudgetAssumptions:
    portfolio_value: Optional[PortfolioValueAssumption] = None
    maximum_single_structure_loss_fraction: Optional[ExactRational] = None
    maximum_repeated_loss_fraction: Optional[ExactRational] = None
    risk_budget_methodology: Optional[str] = None
```

Missing values are permitted so the assessment can return a valid
`data_insufficient` result. Every non-`None` value requires its exact public
type. Both boundary fractions must be within `[0, 1]`.
`risk_budget_methodology`, when present, requires exact type `str`, is
stripped, and must remain nonempty. Lists, mappings, floats, `Decimal` ratios,
and integer substitutes are not silently accepted.

The exact repeated-bet count comes only from the StructureCosts dependency and
is not duplicated in this record.

### 4.3 Status and reason enums

```python
class AffordabilityStatus(str, Enum):
    AFFORDABLE = "affordable"
    NOT_AFFORDABLE = "not_affordable"
    DATA_INSUFFICIENT = "data_insufficient"
```

The reason enum has this exact declaration order:

```python
class AffordabilityReasonCode(str, Enum):
    MISSING_PORTFOLIO_VALUE = "missing_portfolio_value"
    MISSING_SINGLE_LOSS_BOUNDARY = "missing_single_loss_boundary"
    MISSING_REPEATED_LOSS_BOUNDARY = "missing_repeated_loss_boundary"
    MISSING_RISK_BUDGET_METHODOLOGY = "missing_risk_budget_methodology"
    SINGLE_LOSS_EXCEEDS_BOUNDARY = "single_loss_exceeds_boundary"
    REPEATED_LOSS_EXCEEDS_BOUNDARY = "repeated_loss_exceeds_boundary"
```

This state model is separate from `CandidateState`, `ScreeningReasonCode`, and
current synthetic screening thresholds.

### 4.4 `StructureAffordabilityEvidence`

```python
@dataclass(frozen=True)
class StructureAffordabilityEvidence:
    structure: OptionStructure
    as_of_date: date
    assumptions: RiskBudgetAssumptions
    single_position_maximum_loss: Decimal
    repeated_bet_count: int
    repeated_aggregate_maximum_loss: Decimal
    single_loss_fraction: Optional[ExactRational]
    repeated_loss_fraction: Optional[ExactRational]
    status: AffordabilityStatus
    reason_codes: Tuple[AffordabilityReasonCode, ...]
```

The record intrinsically validates and reconstructs every nested object and
field. It requires the exact supported `OptionStructure` grammar, exact date,
exact assumption record, positive finite exact `Decimal` loss amounts, and an
exact positive built-in repeated count; Boolean rejects.

It enforces exact arithmetic relationships, optional-value invariants, the
exact status/reason relationship, and a deterministic enum-order reason tuple.
It performs no list-to-tuple conversion and does not use ordinary dataclass
equality as its trust boundary. Forged objects that bypassed `__post_init__`
reject.

### 4.5 Result wrapper and producer

```python
@dataclass(frozen=True)
class StructureAffordabilityAssessmentResult:
    record: StructureAffordabilityEvidence
    lineage: CalculationLineage
```

The producer is:

```python
assess_structure_affordability(
    calculation_id,
    structure_costs_result,
    risk_budget_assumptions,
    calculated_at,
)
```

Arguments use exact types. The calculation ID is stripped and nonempty. The
dependency has exact type `StructureCostsTransformationResult`; assumptions
have exact type `RiskBudgetAssumptions`; calculation time has exact type
timezone-aware `datetime` and is normalized to UTC. There is no internal
clock.

The calculation ID differs from the dependency ID and every normalized input
ID. Result time does not precede the dependency or normalized-input times.
Complete dependency reconstruction and validation precedes affordability
arithmetic and any new evidence or lineage construction.

## 5. Exact arithmetic

Let:

```text
C = exact maximum_loss_exact from StructureCosts v0.2
R = exact reviewed repeated_bet_count
P = exact caller portfolio-value Decimal
Smax = declared maximum single-structure loss fraction
Rmax = declared maximum repeated-loss fraction
```

Calculate:

```text
single_position_maximum_loss = C
repeated_aggregate_maximum_loss = C × R
single_loss_fraction = C / P
repeated_loss_fraction = (C × R) / P
```

`C × R` is constructed exactly from the Decimal coefficient/exponent and
integer arithmetic. Ratios use exact rational arithmetic. No float, rounded
Decimal division, numeric root finding, ambient Decimal-context dependence,
or arbitrary coefficient or exponent cap is permitted. The caller's complete
Decimal context is unchanged on success and ordinary failure.

Actual loss fractions may exceed one. Declared boundary fractions may not.

## 6. Outcome rules

The four required assumptions for a conclusive result, in precedence order,
are:

1. portfolio-value assumption;
2. maximum single-structure loss fraction;
3. maximum repeated-loss fraction; and
4. risk-budget methodology.

If any is absent, status is `DATA_INSUFFICIENT`; reason codes contain exactly
all missing-assumption codes in enum declaration order; and no boundary breach
is evaluated or included. Calculated loss fractions are present when portfolio
value exists and are `None` when it is absent.

With all required assumptions:

```text
AFFORDABLE when:
single_loss_fraction <= maximum_single_structure_loss_fraction
and
repeated_loss_fraction <= maximum_repeated_loss_fraction
```

Equality is affordable. `NOT_AFFORDABLE` applies when either complete
comparison exceeds its boundary, with exactly the breached boundary code or
codes in enum declaration order. `AFFORDABLE` has an empty reason tuple.

Missing valid data is not an error. Wrong type, malformed value, nonfinite
value, invalid range, chronology mismatch, dependency inconsistency, or legacy
portfolio-value contradiction raises `TypeError` or `ValueError`.

## 7. Provenance and legacy compatibility

`OptionStructure.assumed_portfolio_value` remains provisional legacy metadata,
not arithmetic authority. When a new `PortfolioValueAssumption` is present,
its exact Decimal amount must equal:

```text
Decimal(str(structure.assumed_portfolio_value))
```

This is compatibility consistency only. Arithmetic uses the exact new Decimal
assumption and never the legacy float. A mismatch is contradictory input and
raises `ValueError`; the legacy field alone is insufficient for a conclusive
result.

The dependency must be completely and intrinsically reconstructed before use.
Caller assumptions are canonical parameters, not fabricated normalized
market-data observations. The new lineage inputs exactly equal the dependency
lineage inputs.

## 8. Lineage and canonical schema

The exact lineage identity is:

```text
calculation_type = structure_affordability
methodology_id = exact-bounded-loss-against-declared-risk-fractions
methodology_version = v0.1
```

Canonical parameters are serialized only by
`canonicalize_lineage_parameters` and contain exactly these ten top-level
keys:

```text
schema_version
output_architecture
currency
risk_scope
structure_costs_dependency
risk_budget_assumptions
calculation_values
affordability_rule
outcome
limitations
```

The fixed declarations are:

```text
schema_version = v0.1
output_architecture = standalone_structure_affordability_evidence
currency = USD
```

### 8.1 `risk_scope`

The mapping contains exactly:

```text
single_position
repeated_attempts
annual_budget
existing_committed_exposure
inverse_sizing
```

Its declarations state one already-specified structure; equal repeated
attempts, not concurrency or annual frequency; annual budget excluded;
committed exposure excluded; and inverse sizing excluded.

### 8.2 `structure_costs_dependency`

The mapping contains exactly:

```text
calculation_id
calculation_type
methodology_id
methodology_version
calculated_at
parameters_json
quality_flags
input_rule
```

Dependency identity is exactly:

```text
structure_costs
exact-structure-costs
v0.2
```

The complete dependency `parameters_json` is retained unchanged.

### 8.3 `risk_budget_assumptions`

The mapping contains exactly:

```text
portfolio_value
maximum_single_structure_loss_fraction
maximum_repeated_loss_fraction
risk_budget_methodology
legacy_portfolio_value_correspondence
missing_assumption_policy
```

A nonmissing `portfolio_value` mapping contains exactly:

```text
amount
as_of_date
methodology
currency
```

Its currency is exactly `USD`.

### 8.4 `calculation_values`

The mapping contains exactly:

```text
single_position_maximum_loss
repeated_bet_count
repeated_aggregate_maximum_loss
portfolio_value
single_loss_fraction
repeated_loss_fraction
maximum_single_structure_loss_fraction
maximum_repeated_loss_fraction
```

### 8.5 `affordability_rule` and `outcome`

`affordability_rule` contains exactly:

```text
required_assumptions
single_comparison
repeated_comparison
complete_rule
equality_boundary
incomplete_precedence
```

`outcome` contains exactly:

```text
status
reason_codes
```

Every rational mapping contains exactly:

```text
numerator
denominator
```

### 8.6 Strict canonical validation

Strictly reject missing or extra keys, duplicate JSON keys, JSON floats,
malformed Decimal/date/datetime/rational encodings, Boolean or integer
substitutions, integer subclasses, unreduced fractions, nonpositive
denominators, noncanonical encodings, wrong declarations, wrong ordering,
public-record disagreement, and dependency disagreement.

The result wrapper independently reconstructs expected canonical parameters
and requires byte-identical retained `parameters_json`. It reconstructs every
nested public object rather than trusting ordinary dataclass equality.

## 9. Quality flags

The new lineage:

- always includes `ASSUMPTION_APPLIED`;
- includes `INCOMPLETE_INPUT_USED` if and only if status is
  `DATA_INSUFFICIENT`;
- propagates `INTERPOLATED`, `CORRECTION_SELECTED`, and
  `COMPOSITE_INPUT_USED` if and only if present in the dependency;
- never includes `DECIMAL_TO_FLOAT_CONVERTED`, `ANNUALIZED`, or
  `ADJUSTED_INPUT_USED`; and
- stores flags in canonical enum declaration order.

## 10. Explicit exclusions

The contract creates no annual risk-budget field, absolute USD budget input,
budget utilization, remaining-budget output, quantity calculation, maximum
affordable quantity, trade recommendation, portfolio optimization, holdings or
committed-exposure model, probability or expected-return calculation,
screening state or reason, candidate assembly, report integration,
position-management plan, provider or service access, monitoring, alerting,
execution, generic assessment framework, or new exception hierarchy.

Existing synthetic screening thresholds remain unchanged and explicitly
non-authoritative for caller affordability.

## 11. Implemented BUILD scope and required tests

The completed BUILD is limited to the
`convexity_hunter.risk_assessment` module and its focused tests. It implements
exactly the frozen API,
records, arithmetic, outcome precedence, dependency reconstruction, canonical
schema, lineage, and quality-flag behavior without changing screening,
candidate assembly, reporting, package-root exports, or the completed
Milestone 4 contract.

Required tests must independently cover:

- exact public types, normalization, immutable records, and forged nested
  objects;
- supported structure grammar and exact dependency reconstruction;
- missing-assumption combinations and enum-order reason precedence;
- equality and breach outcomes for each and both boundaries, including zero;
- exact Decimal-to-rational arithmetic for large coefficients and exponents
  without ambient-context mutation;
- legacy portfolio-value equality and contradiction;
- date, ID, input, and calculation-time chronology;
- literal canonical parameter schema, byte-level golden serialization,
  duplicate-key and noncanonical-encoding rejection;
- public-record, dependency-disclosure, lineage-input, and quality-flag
  tampering;
- unchanged transformation and market-data export counts; and
- explicit absence of screening, candidate, report, provider, service,
  holding, sizing, recommendation, and execution behavior.
