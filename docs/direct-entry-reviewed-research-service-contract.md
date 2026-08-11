# Direct Entry Reviewed-Research Service Contract v0.2

## Purpose and correction

This Tier-A contract composes source-backed exact-contract verification,
reviewed-artifact candidate assembly, deterministic screening, optional
position-management, and the Chinese report for one caller-selected structure.

Exact listed-contract identity is the entry gate. Complete research readiness
is not. Authentic cost and liquidity artifacts remain strict when present, but
their absence may pass to the existing partial assembly and deterministic
`DATA_INSUFFICIENT` path.

## Public API and result

The direct module exports exactly:

```text
DirectEntryReviewedResearchServiceResult
run_direct_entry_reviewed_research_service
```

The frozen result contains exactly, in order:

```python
exact_contract_verification: DirectEntryExactContractVerification
research_readiness_verification: Optional[
    DirectEntryResearchReadinessVerification
]
offline_service_result: OfflineSingleStructureServiceResult
```

The package root exports neither name.

## Signature

The service has 24 parameters. It preserves the existing 21 candidate-assembly
inputs, adds `contract_references` immediately after `structure`, then accepts
the existing exact `ScreeningPolicy` and optional
`PositionManagementPlanRequest`:

```text
calculation_id
candidate_id
state
state_rationale
as_of_date
hypothesis
structure
contract_references
volatility_environment_result
tail_pricing_result
structure_liquidity_result
structure_costs_result
scenario_valuation_result
expiration_payoff_threshold_result
structure_affordability_result
evidence
falsification_conditions
missing_data
false_positive_reasons
ai_interpretation
human_review_questions
calculated_at
screening_policy
position_management_plan_request = None
```

## Frozen delegation order

The service performs only:

1. `verify_direct_entry_exact_contracts(structure, contract_references)`;
2. if and only if both costs and liquidity are present,
   `verify_direct_entry_research_readiness(structure, costs, liquidity)`;
3. `assemble_candidate_research_record(...)`, using the exact verified
   structure and the caller's seven artifact values unchanged, including
   `None`;
4. `run_offline_single_structure_service(...)`;
5. construction of the three-field result retaining both verification
   sidecars and the offline result.

If only one of costs or liquidity is present, research-readiness verification
is absent and the assembler remains the authority for the present artifact and
state-compatible missing-data disclosure. If both are absent, neither is
fabricated. If both are present, the strict research-readiness proof is
retained.

Delegated failures propagate unchanged and short-circuit later stages. The
service generates no IDs, times, evidence, missing-data prose, state,
screening rule, calculations, provider calls, or report content.

## Real minimal loop

The authorized minimal result is:

```text
real exact contract reference
    -> exact-contract verification
    -> available reviewed artifacts plus explicit None values
    -> partial CandidateResearchRecord
    -> DATA_INSUFFICIENT ScreeningDecision
    -> deterministic zh-CN report
```

`DATA_INSUFFICIENT` still requires nonempty caller/product `missing_data`, and
the scanner's canonical missing-reason order remains authoritative. No
position-management plan is permitted for the resulting state.

## Exclusions

No provider adapter, data-source expansion, structure generation, pricing,
generic orchestration, recommendation, persistence, monitoring, alerting, or
execution is added by this service correction.
