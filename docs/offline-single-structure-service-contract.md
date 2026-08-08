# Offline Single-Structure Service Contract

## 1. Status and authority

This document is the canonical A-level contract freeze for the deterministic
offline single-structure service. It is documentation-only. It does not
authorize implementation, test changes, package-root exports, staging,
committing, or pushing.

The service is a narrow orchestration boundary for one already-reviewed
`CandidateResearchRecordAssemblyResult`. It combines the existing screening,
prospective position-management-plan, and Chinese-report producers without
creating a second assembly path or a new calculation authority.

The authoritative direct module is:

```text
convexity_hunter.offline_service
```

The service is not exported from the `convexity_hunter` package root.

## 2. Public API and export counts

The direct module has exactly three public names, in this order:

1. `PositionManagementPlanRequest`
2. `OfflineSingleStructureServiceResult`
3. `run_offline_single_structure_service`

The module's `__all__` contains exactly those three names, in that order. The
feature adds zero package-root exports. Dependency types and implementation
helpers are private implementation details of the direct module and do not
increase this public count.

No other public class, enum, function, constant, policy, result, lineage type,
locale selector, or convenience wrapper belongs to this contract.

## 3. Frozen dataclasses

Both service-owned records are frozen dataclasses with no additional fields.
Field order is part of the API and must be preserved by introspection,
construction, equality, and serialization-oriented tests.

### 3.1 `PositionManagementPlanRequest`

```python
@dataclass(frozen=True)
class PositionManagementPlanRequest:
    calculation_id: str
    conditions: Tuple[
        Union[
            QuantitativePositionManagementCondition,
            QualitativePositionManagementCondition,
        ],
        ...,
    ]
    calculated_at: datetime.datetime
```

The request is caller-supplied and complete only when this object supplies all
three required fields. `None` is the only value that disables plan creation.
The request does not generate or infer a calculation ID, conditions, a
timestamp, a policy, a candidate state, or market data.

The field values use the exact declared shape: `calculation_id` is a built-in
`str`, `conditions` is a built-in tuple containing only the two exact existing
condition types, and `calculated_at` is a `datetime.datetime`. `calculation_id`
and `conditions` are passed to the existing plan producer without service-level
substitution or generation.

`calculated_at` must be timezone-aware. Existing
`create_position_management_plan` normalization and validation remain
authoritative for its accepted timezone/canonical form and all semantic
condition, assembly-state, and plan validation. The service does not obtain a
clock or pre-validate by replaying that producer.

### 3.2 `OfflineSingleStructureServiceResult`

```python
@dataclass(frozen=True)
class OfflineSingleStructureServiceResult:
    assembly_result: CandidateResearchRecordAssemblyResult
    screening_decision: ScreeningDecision
    position_management_plan_result: Optional[PositionManagementPlanResult]
    report_markdown: str
```

The result retains the exact supplied `assembly_result` object. It retains the
exact `ScreeningDecision` returned by `screen_candidate` and, when a plan is
requested, the exact `PositionManagementPlanResult` returned by
`create_position_management_plan`. It does not create or attach a new
calculation lineage, calculation ID, timestamp, state, or market-data record.

`report_markdown` is the deterministic Chinese report returned by the existing
renderer. A report is required on both the no-plan and plan-enabled paths.

## 4. Function signature

The only service function is:

```python
def run_offline_single_structure_service(
    assembly_result: CandidateResearchRecordAssemblyResult,
    screening_policy: ScreeningPolicy,
    position_management_plan_request: Optional[PositionManagementPlanRequest] = None,
) -> OfflineSingleStructureServiceResult:
```

There is no locale parameter and no service-level default screening policy.
The caller supplies the already-reviewed assembly result and the screening
policy. The caller enables a plan only by supplying a complete
`PositionManagementPlanRequest`.

## 5. Exact input boundary

Before any downstream producer is called, the service applies exact-type
boundaries to its direct inputs:

- `type(assembly_result) is CandidateResearchRecordAssemblyResult`;
- `type(screening_policy) is ScreeningPolicy`; and
- `position_management_plan_request is None` or
  `type(position_management_plan_request) is PositionManagementPlanRequest`.

The service accepts no subclass, replacement record, separate candidate, or
partial plan-request mapping at these boundaries. Nested validation and
integrity verification remain owned by the existing reviewed producers and
results. The service does not reconstruct or mirror the 21-argument
`assemble_candidate_research_record` call.

## 6. Required orchestration order

The service has one fixed sequence. It must not branch on screening state to
skip required work, reorder producers, or replace one producer with an
equivalent local calculation.

### Step 0 — Service boundary

Apply the exact direct-input boundaries in Section 5. A boundary failure ends
the call before any screening, plan, or rendering call.

### Step 1 — Always screen

Call exactly:

```python
decision = screen_candidate(assembly_result.record, screening_policy)
```

Screening is always required, including when the assembly record is
`REJECT`, `DATA_INSUFFICIENT`, `WATCH`, or `INVESTIGATE`. The supplied
research-record state remains separate from `decision.proposed_state`; neither
is copied into the other and the assembly record is not mutated.

### Step 2 — Optionally create the plan

When `position_management_plan_request is None`, do not call the plan
producer and set the result field to `None`.

When a request is supplied, call exactly:

```python
plan = create_position_management_plan(
    position_management_plan_request.calculation_id,
    assembly_result,
    position_management_plan_request.conditions,
    position_management_plan_request.calculated_at,
)
```

The authoritative existing plan producer governs eligibility using the assembly
candidate state together with its existing condition-category cardinality,
artifact-prerequisite, and condition-grammar requirements. The service does not
inspect, infer, or substitute the separate `ScreeningDecision` to gate or
replace plan eligibility, or manufacture plan state. If the existing plan
producer rejects the assembly state, request conditions, or any of those
existing prerequisites, that producer exception is authoritative.

### Step 3 — Always render Chinese Markdown

After screening and any requested plan construction succeed, call exactly:

```python
report_markdown = render_candidate_markdown(
    assembly_result.record,
    locale="zh-CN",
    screening_decision=decision,
    position_management_plan_result=plan,
)
```

The literal `locale="zh-CN"` is frozen. The service does not expose locale
input, choose a locale dynamically, render English, render a second report, or
render the plan independently. Screening and plan results are passed
separately to the renderer.

### Step 4 — Return the service result

Return one `OfflineSingleStructureServiceResult` with the four fields in the
frozen order from Section 3.2. No additional work occurs after rendering.

## 7. State and producer separation

The service preserves three separate concepts:

1. the caller-supplied state retained by `assembly_result.record`;
2. the independently calculated `ScreeningDecision`; and
3. the prospective `PositionManagementPlanResult`, when caller-enabled and
   permitted by the existing assembly-state/condition contract.

Screening is not a plan prerequisite beyond being mandatory service work. A
screening result of `REJECT` or `DATA_INSUFFICIENT` does not itself disable or
replace a caller-requested plan; the existing plan producer and the assembly
record's state remain authoritative. Conversely, a plan is never synthesized
from a screening result when the caller supplies no request.

The service does not call `assemble_candidate_research_record`, any upstream
transformation or affordability producer, a provider adapter, or a second
renderer, and it does not implement a second screening evaluator. It consumes
the reviewed assembly result as-is.

## 8. Validation and error semantics

Validation and failures follow the same order as execution:

1. service direct-input exact-type boundary;
2. `screen_candidate` validation and existing screening exceptions;
3. `create_position_management_plan` validation and existing plan-producer
   exceptions, only when a request is supplied; and
4. `render_candidate_markdown` validation and existing rendering exceptions.

The service must not catch, swallow, translate, relabel, or reorder these
exceptions. If a stage raises, later stages are not called. A screening error
therefore precedes any plan or rendering error; a plan error precedes any
rendering error. The service adds no alternate error taxonomy and no partial
result.

The service must not use screening to pre-validate or reinterpret plan
eligibility, and must not duplicate producer validation in a way that changes
exception order or exception identity. Existing producer behavior is the
authority for nested records, conditions, timestamps, state prerequisites,
plan binding, and report compatibility.

## 9. Determinism, purity, and offline scope

For the same unchanged input object graph, policy, and optional request, the
service returns the same frozen result values and byte-for-byte identical
`report_markdown`, or raises the same stage-specific existing exception. It
does not depend on process time, local timezone, randomness, environment
variables, filesystem state, network state, provider state, persistence, or
framework lifecycle.

The service is pure orchestration:

- no I/O, network, provider, API-key, credential, or HTTP access;
- no system clock or generated timestamp;
- no generated ID, condition, state, policy, market data, or report locale;
- no mutation of the assembly result, candidate record, policy, request,
  screening decision, or plan result;
- no persistence, cache, monitoring, scheduling, alerting, CLI, web, or
  framework integration; and
- no recommendation, ranking, sizing, ownership claim, order management, or
  execution behavior.

All numerical, screening, plan, lineage, and report semantics remain delegated
to the existing contracts:
[`candidate-assembly-contracts.md`](candidate-assembly-contracts.md),
[`screening-policy.md`](screening-policy.md),
[`position-management-contracts.md`](position-management-contracts.md), and
the existing report contract. This service introduces no new calculation or
lineage authority.

## 10. BUILD and test acceptance criteria

This section defines the later BUILD gate. It is not implementation work in
this documentation-only freeze.

The BUILD implementation and focused tests are accepted only when they prove
all of the following with independent fixed fixtures and call-trace spies:

- the direct module, `__all__` order/count, three public names, result/request
  field order, frozen dataclass behavior, annotations, function signature,
  and zero package-root exports;
- exact direct-input boundary rejection before any downstream call;
- the no-plan trace: boundary → screening → Chinese renderer, with no plan
  producer call;
- the plan trace: boundary → screening → plan producer → Chinese renderer,
  with the exact arguments and literal `locale="zh-CN"` shown above;
- screening is called for every valid assembly state, and the plan path is
  never gated by the returned screening state;
- request values, assembly result, producer-returned decision, and
  producer-returned plan result are retained by identity where specified, with
  no assembly replay or local replacement calculation;
- the report is always present and is the renderer's returned string;
- each stage's exception stops later calls and preserves the existing
  exception class/message semantics without swallowing or relabeling;
- repeated identical calls are deterministic and do not mutate inputs or
  introduce clock, I/O, provider, persistence, or generated-value behavior;
- adversarial tests cover alternate assembly states versus screening decisions,
  `None` versus complete requests, invalid direct types, and independent
  recomputation of the expected call trace; and
- the focused tests, the existing full suite, API/export checks, and
  `git diff --check` pass without changing README, source outside the later
  service implementation, or unrelated tests.

## 11. Explicit non-goals

This contract does not define or authorize:

- active discovery, event intelligence, provider access, market-data
  retrieval, option-chain access, structure generation, or pricing production;
- a second candidate-assembly API or any change to the existing 21-argument
  assembly producer;
- screening-policy thresholds, reason codes, plan condition grammar, lineage
  schema, or report prose beyond their existing authoritative contracts;
- current position evaluation, trigger monitoring, alerts, scheduling,
  persistence, brokerage, automatic monetization, or automatic exit; or
- package-root exports, CLI/framework integration, or an English service report.
