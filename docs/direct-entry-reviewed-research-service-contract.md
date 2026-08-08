# Deterministic Direct-Entry Reviewed-Research Service Contract

## 1. Status and scope

This document is the canonical documentation-only contract freeze at base
`e6f951eacf89ada5144f1b9b04db3f44a1c593bd`. It authorizes no source or test
change, staging, commit, push, or network access. The capability is for
Python 3.9.

The service composes one complete caller-supplied `OptionStructure`, its
reviewed exact-structure verification, one caller-supplied candidate-research
assembly, and the existing offline single-structure service. It is an
orchestration boundary only. Success means only an offline reviewed-research
composition for that complete caller-supplied structure; it is not an
eligibility, status, or approval claim.
Neither retained assembly state, offline screening decision, nor optional plan
is promoted into such a service-level claim.

## 2. Public API and export boundary

The authoritative module is:

```text
convexity_hunter.direct_entry_reviewed_research_service
```

Its `__all__` is exactly these names, in this order:

```python
__all__ = (
    "DirectEntryReviewedResearchServiceResult",
    "run_direct_entry_reviewed_research_service",
)
```

The capability adds zero package-root exports. No other public class,
function, result, policy, enum, constant, alias, or convenience wrapper is
part of this freeze.

## 3. Frozen result and exact signature

The service-owned result is exactly this frozen record, with no additional
fields and this field order:

```python
@dataclass(frozen=True)
class DirectEntryReviewedResearchServiceResult:
    direct_entry_verification: DirectEntryExactStructureVerification
    offline_service_result: OfflineSingleStructureServiceResult
```

Direct construction is frozen and exactly annotated as above. It is an
orchestration result record, not a second authenticity or eligibility
authority: construction must not replay delegated verification, screening,
plan, lineage, or report logic, derive a new claim, or replace either
delegated result.

The only service function has exactly these first 21 parameters, names,
order, and `object` annotations, mirroring
`assemble_candidate_research_record`:

```python
def run_direct_entry_reviewed_research_service(
    calculation_id: object,
    candidate_id: object,
    state: object,
    state_rationale: object,
    as_of_date: object,
    hypothesis: object,
    structure: object,
    volatility_environment_result: object,
    tail_pricing_result: object,
    structure_liquidity_result: object,
    structure_costs_result: object,
    scenario_valuation_result: object,
    expiration_payoff_threshold_result: object,
    structure_affordability_result: object,
    evidence: object,
    falsification_conditions: object,
    missing_data: object,
    false_positive_reasons: object,
    ai_interpretation: object,
    human_review_questions: object,
    calculated_at: object,
    screening_policy: ScreeningPolicy,
    position_management_plan_request: Optional[PositionManagementPlanRequest] = None,
) -> DirectEntryReviewedResearchServiceResult:
```

There are no additional parameters or keyword-only substitutions. The
displayed optional plan request is the only service-level default.

## 4. Exact orchestration order and identity

The service performs exactly these calls, with no service-level prevalidation
before the first call or between delegated stages:

1. Verify the direct entry, in this exact argument order:

   ```python
   direct_entry_verification = verify_direct_entry_exact_structure(
       structure,
       structure_costs_result,
       structure_liquidity_result,
   )
   ```

   The verifier-retained values must preserve the original identities:

   ```text
   direct_entry_verification.structure is structure
   direct_entry_verification.costs_result is structure_costs_result
   direct_entry_verification.liquidity_result is structure_liquidity_result
   ```

2. Assemble the candidate research record with all original 21 caller values
   in the existing assembler order. The three direct-entry positions use the
   verifier-retained objects, while retaining their original identities:

   ```python
   assembly_result = assemble_candidate_research_record(
       calculation_id,
       candidate_id,
       state,
       state_rationale,
       as_of_date,
       hypothesis,
       direct_entry_verification.structure,
       volatility_environment_result,
       tail_pricing_result,
       direct_entry_verification.liquidity_result,
       direct_entry_verification.costs_result,
       scenario_valuation_result,
       expiration_payoff_threshold_result,
       structure_affordability_result,
       evidence,
       falsification_conditions,
       missing_data,
       false_positive_reasons,
       ai_interpretation,
       human_review_questions,
       calculated_at,
   )
   ```

   In particular, the assembler receives liquidity before costs, even though
   the verifier receives costs before liquidity.

3. Run the offline service exactly as follows, preserving the caller's
   policy and optional request objects:

   ```python
   offline_service_result = run_offline_single_structure_service(
       assembly_result,
       screening_policy,
       position_management_plan_request,
   )
   ```

4. Return exactly one result record:

   ```python
   return DirectEntryReviewedResearchServiceResult(
       direct_entry_verification,
       offline_service_result,
   )
   ```

The returned record retains both delegated result identities. The existing
offline result also retains the exact `assembly_result` identity. The service
does not copy, reconstruct, serialize, normalize, or substitute any caller
value or delegated result.

Failures propagate unchanged and short-circuit the sequence. A verifier
failure prevents assembly and offline execution; an assembler failure prevents
offline execution; and an offline-service failure produces no service result.
The service catches, translates, wraps, retries, or replaces no delegated
failure.

## 5. Delegated authority and non-authority

Each existing boundary remains authoritative for its own concerns:

- `verify_direct_entry_exact_structure` owns exact structure verification,
  authentic costs, authentic liquidity, and their correspondence.
- `assemble_candidate_research_record` owns the candidate record, reviewed
  artifacts, narrative fields, candidate state compatibility, and assembly
  lineage.
- `run_offline_single_structure_service` owns exact `ScreeningPolicy` and
  optional `PositionManagementPlanRequest` types, screening, optional plan
  creation, and the deterministic `zh-CN` report.

The new service owns none of those validations and performs no eligibility,
status, approval, authenticity, lineage, numerical, policy, screening,
report, or plan replay. It generates no IDs, times, or data, obtains no clock,
and does not mutate any input, nested value, or delegated result.

The caller may supply either `None` or a plan request. Costs and liquidity are
mandatory because direct-entry verification requires both. A valid partial
assembly may omit only other artifacts where the existing assembler permits
their absence; the service does not infer completeness or alter the
caller-supplied state.

## 6. Explicit exclusions

The capability excludes:

- provider, network, or option-chain retrieval;
- incomplete-description resolution;
- standard-monthly, DTE, Delta, ATM, or structure generation;
- pricing;
- Event Intelligence or Skills;
- UI or CLI;
- persistence;
- monitoring or alerts; and
- execution.

It also adds no proof replay, new lineage or numerical authority, new policy
authority, local screening logic, local report logic, or local plan logic.

## 7. Later BUILD boundary

Only a separately authorized later BUILD may add the following new files:

```text
src/convexity_hunter/direct_entry_reviewed_research_service.py
tests/test_direct_entry_reviewed_research_service.py
```

No existing source, package-root export, fixture, unrelated test, or other
documentation may be changed. At BUILD completion only,
`docs/current-checkpoint.md` and `docs/project-state.md` may receive
status-only updates; those updates may not introduce new scope or contract.

## 8. Acceptance-test contract

Focused tests must independently assert:

- the exact module API, `__all__` order, frozen result field order and exact
  annotations, exact 23-parameter signature and annotations, and zero
  package-root exports;
- the exact four-stage trace and argument identities, including the
  verifier's costs-then-liquidity order and the assembler's existing
  liquidity-then-costs order;
- unchanged failure propagation and short-circuiting at verification,
  assembly, and offline-service stages;
- a complete assembly and a valid partial assembly that still supplies costs
  and liquidity but omits another assembler-optional artifact, both `None` and
  plan-request paths, and retention of verifier, assembly, and offline result
  identities;
- absence of local prevalidation, replay, generated IDs/times/data, mutation,
  and any provider or upstream retrieval call;
- deterministic behavior for repeated calls with fixed delegated outcomes;
  and
- absence of any service-level eligibility, status, or approval claim.
