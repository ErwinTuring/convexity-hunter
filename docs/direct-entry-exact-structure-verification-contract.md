# Direct Entry Verification Contract v0.2

## Status and correction

This Tier-A contract supersedes the former exact-structure verification
contract. The former boundary conflated two independent claims: that every
caller-selected listed contract has source-backed exact identity, and that the
structure already has complete reviewed cost and liquidity evidence. That
coupling prevented the existing partial candidate path from producing an
honest `DATA_INSUFFICIENT` result.

The corrected module keeps those claims separate. It does not weaken any
market-data, cost, liquidity, assembly, screening, or reporting authority.

## Public API

The direct module `convexity_hunter.direct_entry_verification` exports exactly,
in order:

```text
DirectEntryExactContractVerification
verify_direct_entry_exact_contracts
DirectEntryResearchReadinessVerification
verify_direct_entry_research_readiness
```

None is exported from the package root.

## Exact-contract verification

```python
@dataclass(frozen=True)
class DirectEntryExactContractVerification:
    structure: OptionStructure
    contract_references: tuple[OptionContractReference, ...]

def verify_direct_entry_exact_contracts(
    structure: OptionStructure,
    contract_references: tuple[OptionContractReference, ...],
) -> DirectEntryExactContractVerification:
    ...
```

The structure, every nested leg, the tuple, and every reference require exact
types and intrinsic reconstruction. The tuple has exactly one reference per
leg in leg order. Each source-backed
provider-reference or system-composite record is intrinsically reconstructed
and must match the corresponding leg's underlying symbol, expiration,
call/put, exact `Decimal(str(leg.strike))`, and provider-supplied contract
multiplier.

This layer proves that the supplied structure corresponds to source-backed
exact contract identity. It does not prove standard or unadjusted deliverable
status, complete contract terms, quote freshness, liquidity, costs, analytics,
research readiness, or eligibility. An `INCOMPLETE` contract reference may
therefore pass identity verification without being upgraded or losing its
quality flag. Missing deliverable evidence remains missing downstream.

No provider, network, credential, discovery, transformation, or inference call
is permitted.

## Research-readiness verification

```python
@dataclass(frozen=True)
class DirectEntryResearchReadinessVerification:
    structure: OptionStructure
    costs_result: StructureCostsTransformationResult
    liquidity_result: StructureLiquidityTransformationResult

def verify_direct_entry_research_readiness(
    structure: OptionStructure,
    costs_result: StructureCostsTransformationResult,
    liquidity_result: StructureLiquidityTransformationResult,
) -> DirectEntryResearchReadinessVerification:
    ...
```

This preserves the former strict behavior under a truthful name. All three
inputs require exact types; both reviewed wrappers are intrinsically replayed;
both records must match the supplied structure and share `as_of_date`. Neither
artifact is optional in this verifier. Existing `StructureCosts` and
`StructureLiquidity` evidence standards remain unchanged.

## Failure and scope boundary

Malformed, contradictory, extra, missing, reordered, or non-source-backed
contract references fail closed. Present but malformed costs or liquidity fail
under their existing authorities. Absence is represented only by `None` at the
candidate-service boundary and is never replaced with inferred evidence.

This correction adds no structure generation, pricing, data source,
orchestration framework, recommendation, monitoring, or execution behavior.
