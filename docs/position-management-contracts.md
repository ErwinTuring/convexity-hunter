# Position-Management Plan Contract v0.1

## 1. Status and work-unit identity

This document is the authoritative product and architecture clarification for
the standalone work unit named **Position-Management Plan Contract**. It
resolves the accepted product-contract blockers reported by the first formal
read-only preflight, which returned `PREFLIGHT RESULT: BLOCKED`.

The standalone implementation is complete. It was independently reviewed,
corrected, and targeted re-reviewed with a passing result. The implementation
and its focused tests are intentionally limited to this work unit; screening,
reporting, monitoring, and execution remain outside its scope.

The work unit is intentionally unnumbered. It is not Milestone 6C, Milestone
7, or a decision that it belongs to Milestone 6.

### Implementation status

The reviewed implementation is frozen in:

`src/convexity_hunter/position_management.py`

with focused tests in:

`tests/test_position_management.py`

The module exports exactly these 11 public names:

`PositionManagementScope`, `PositionManagementCategory`,
`PositionManagementAuthority`, `PositionManagementMetric`,
`PositionManagementComparison`, `PositionManagementQualitativeTrigger`,
`QuantitativePositionManagementCondition`,
`QualitativePositionManagementCondition`, `PositionManagementPlan`,
`PositionManagementPlanResult`, and `create_position_management_plan`.

The exact producer is
`create_position_management_plan(calculation_id, assembly_result, conditions,
calculated_at)`. Its result retains exactly `assembly_result`, `plan`, and
`lineage`; the package root does not re-export the position-management API.
The calculation identity is `position_management_plan` /
`prospective-human-judgment-position-management-plan` / `v0.1`. The final
reviewed baseline is 60 position-management tests, 998 full-suite tests, and
passing independent targeted re-review. The source conforms to the frozen
v0.1 product contract.

## 2. Product identity and scope

The selected product artifact identity is:

`PositionManagementPlan`

Its fixed meaning is:

> prospective research guidance for a hypothetical future long-option
> position, for later human judgment only

The plan has one fixed structural scope:

`prospective_research_guidance`

The scope is not caller-selectable among multiple modes in v0.1. The plan
does not establish that a position exists, that the user owns the structure,
that an order was submitted or filled, that the candidate is recommended, or
that the user should enter a trade.

Its three categories map only to the following human-judgment language:

`monetization  -> consider monetization
reassessment  -> consider reassessment
exit          -> consider exit`

There is no independent free-form action field. A category cannot encode
`sell`, `close now`, `take profit`, `stop out`, or `execute`. This is a
structural restriction, not a disclaimer.

A future evaluator, monitor, alerting system, or report integration requires a
separate work unit.

## 3. Declaration-only behavior

Version 0.1 is a **future-condition declaration only**. The plan declares
conditions anchored to one reviewed candidate assembly; it never evaluates
whether a condition is currently met.

The plan therefore contains none of the following:

- current trigger status;
- pending, met, or not-met status;
- last-evaluated or next-evaluation time;
- monitoring or alert state;
- live position value or live P&L;
- a current executable quote;
- an automatic decision; or
- a system-clock-derived value.

All condition text and thresholds are prospective declarations. No condition
claims that its trigger is true at plan construction time.

## 4. Candidate-state applicability

The plan uses the exact candidate state retained by the reviewed assembly. It
does not change, infer, or replace that state.

| Candidate state | Plan construction | Required categories |
| --- | --- | --- |
| `INVESTIGATE` | Permitted | At least one monetization, one reassessment, and one exit condition; all three categories are nonempty |
| `WATCH` | Permitted | At least one reassessment condition; monetization and exit may be empty |
| `REJECT` | Prohibited | None; research-reopening conditions belong to a separate screening or follow-up contract |
| `DATA_INSUFFICIENT` | Prohibited | None; insufficient evidence does not support responsible prospective guidance |

There is no separate `complete`, `partial`, `not_applicable`, or plan-status
field. Validity is determined directly from this state matrix and the
condition prerequisites.

## 5. Sole reviewed input

The sole reviewed research input is exactly one:

`CandidateResearchRecordAssemblyResult`

The future producer does not accept separate arguments for
`CandidateResearchRecord`, Volatility, Tail, Liquidity, Costs, Scenario
Valuation, Expiration Thresholds, or Affordability. It retains the exact
assembly result, preventing duplicate artifact arguments, identity divergence,
loss of Milestone 4 or 5 sidecars, economic-equivalence substitution, or a
second candidate assembly.

The existing `CandidateResearchRecord` and
`CandidateResearchRecordAssemblyResult` contracts remain unchanged. This work
unit does not modify candidate assembly.

## 6. Condition model

The future implementation uses two closed immutable condition forms:

`QuantitativePositionManagementCondition
QualitativePositionManagementCondition`

A plan contains one combined immutable condition collection. Every item is an
exact instance of one of those two forms. Arbitrary dictionaries, generic
JSON payloads, plugins, registries, expression strings, executable callbacks,
and plain text as quantitative authority are not permitted.

### 6.1 Shared condition identity

Every condition has these conceptual fields, in this order:

`condition_id
category
authority
source_reference
rationale`

`condition_id` uses the canonical grammar
`^[a-z][a-z0-9_]{0,63}$`. It must be an exact built-in `str`, already
lowercase, and unique across the complete plan. It is not whitespace-
normalized into another ID.

`category` has exactly these values and this canonical order:

`monetization
reassessment
exit`

`authority` has exactly these values:

`reviewed_artifact
caller
human_analyst`

AI is not an authority. `source_reference` is required normalized nonempty
text. It identifies the exact reviewed calculation when authority is
`reviewed_artifact`, or the caller/human source, note, policy, or external
reference for the other authorities. It is an audit reference, not a provider
fetch instruction.

`rationale` is required normalized nonempty text supplied by the same
declared authority. It explains why the condition belongs in the plan but
cannot change the category, metric, threshold, comparison, trigger, or action
semantics. AI-authored or AI-interpreted rationale is excluded from v0.1.

### 6.2 Quantitative conditions

The conceptual field order is:

`condition_id
category
metric
comparison
threshold
authority
source_reference
rationale`

The supported metrics, meanings, grammar, authority, and prerequisites are
closed as follows:

| Metric | Meaning | Allowed category and comparison | Threshold and authority | Required reviewed basis |
| --- | --- | --- | --- | --- |
| `net_liquidation_value_multiple` | Future executable net liquidation value after exit cost divided by exact reviewed total entry cost | `monetization` + `greater_than_or_equal` only | Positive finite exact `Decimal`; `caller` or `human_analyst` | Exact reviewed total entry cost; no threshold is generated from Milestone 4 |
| `remaining_dte` | Calendar days remaining until reviewed structure expiration | `reassessment` + `less_than_or_equal` only | Exact built-in integer, `0 <= threshold < reviewed DTE at plan as_of_date`; `caller` or `human_analyst` | Reviewed structure expiration and plan as-of date |
| `bid_ask_spread_fraction` | Future absolute bid-ask spread divided by future quoted midpoint | `reassessment` or `exit` + `greater_than_or_equal` | Nonnegative finite exact `Decimal`; `caller` or `human_analyst` | Reviewed Structure Liquidity evidence establishes identity and current basis |
| `atm_iv` | Future ATM implied volatility under the same disclosed methodology identity | `monetization` or `reassessment` + either comparison | Positive finite exact `Decimal`; `caller` or `human_analyst` | Reviewed Volatility Environment evidence; no historical-value-generated threshold |
| `skew_percentile` | Future structure-expiration skew percentile under the same disclosed methodology | `monetization` or `reassessment` + either comparison | Exact `Decimal` in inclusive `[0, 1]`; `caller` or `human_analyst` | Reviewed Tail Pricing evidence and exact structure-expiration slice |
| `single_loss_fraction` | Reviewed single maximum-loss fraction relative to the exact M5 portfolio-value assumption | `reassessment` or `exit` + `greater_than_or_equal` | Exact non-float `Decimal` or exact rational representation selected by formal preflight; `reviewed_artifact` only | Exact supplied Affordability calculation and its single-loss boundary |
| `repeated_loss_fraction` | Reviewed repeated maximum-loss fraction relative to the exact M5 portfolio-value assumption and reviewed repeated-bet count | `reassessment` or `exit` + `greater_than_or_equal` | Exact non-float `Decimal` or exact rational representation selected by formal preflight; `reviewed_artifact` only | Exact supplied Affordability calculation and its repeated-loss boundary |

The only comparisons are inclusive:

`greater_than_or_equal
less_than_or_equal`

There is no strict comparison in v0.1. `remaining_dte` uses an exact
non-Boolean built-in integer. Every other non-risk threshold uses an exact
finite `Decimal`; binary floats and Boolean-as-integer substitutions are
never authoritative. The formal preflight must freeze exact Python
annotations and the canonical tagged representation for the two risk
fractions.

### 6.3 Cost-multiple semantics

These terms remain distinct:

`expiration gross position-value multiple
pre-expiration estimated position-value multiple
pre-expiration net-liquidation-value multiple
after-cost P&L multiple`

Only **pre-expiration net-liquidation-value multiple** is supported as a v0.1
monetization condition. Milestone 4's fixed `1x`, `2x`, `5x`, and `10x`
values are expiration gross position-value thresholds. They exclude exit
cost, are terminal payoff evidence, are not current executable liquidation
triggers, and are not copied automatically into the plan. A plan may use a
separately supplied net-liquidation threshold, but it may not relabel a
Milestone 4 expiration threshold as one. Scenario estimated values are
scenario evidence, not live trigger values.

### 6.4 Qualitative conditions

The conceptual field order is:

`condition_id
category
trigger
authority
source_reference
rationale`

Qualitative authority is `caller` or `human_analyst`. `reviewed_artifact` is
not sufficient for event facts unless a specific reviewed artifact already
establishes that exact fact; the current repository has no such accepted
Event Intelligence record.

The closed trigger grammar is:

| Category | Triggers |
| --- | --- |
| `monetization` | `event_becomes_public`, `underpricing_evidence_disappears` |
| `reassessment` | `event_window_shifts`, `evidence_stale_or_missing`, `contract_adjusted`, `impact_path_materially_changes` |
| `exit` | `event_window_expires_without_hypothesized_change`, `event_cancelled`, `definitive_contrary_resolution`, `exemption_confirmed`, `impact_path_invalidated`, `revised_event_window_not_covered`, `data_loss_prevents_responsible_evaluation` |

These are future trigger declarations. The plan requires an explicit caller
or human declaration and source reference; it does not assert that a trigger
is currently true.

## 7. Event-window boundary

V0.1 does not accept authoritative standalone plan fields for:

`event_window_start
event_window_end
event_status
impact_path_status`

There is no accepted Event Intelligence contract. Event-dependent conditions
use only the closed qualitative triggers, caller or human authority, and an
explicit audit reference. The plan does not calculate a 30-day event buffer,
validate a revised event window, infer cancellation, infer publication, or
infer impact-path invalidation. A future typed Event Intelligence input and
deterministic event-window calculation require a separate contract.

## 8. Affordability and incomplete input

The plan may retain and reference the exact supplied Milestone 5 Affordability
result.

- `AFFORDABLE` does not generate a condition automatically. Risk-fraction
  conditions may reference the exact reviewed boundaries.
- `NOT_AFFORDABLE` does not change candidate state and does not generate an
  automatic exit or trade command. Conditions may reference the exact
  breached boundaries.
- `DATA_INSUFFICIENT` cannot support `single_loss_fraction` or
  `repeated_loss_fraction` when the corresponding exact boundary is
  unavailable. A `WATCH` assembly may still support other reassessment
  conditions.

The plan introduces no second portfolio value, holdings, committed exposure,
position sizing, maximum affordable quantity, annual budget, or brokerage
balance.

An `INVESTIGATE` assembly is complete under Milestone 6B. A `WATCH` assembly
may be partial. A quantitative condition is permitted only when every
reviewed artifact required by its metric is present and intrinsically
complete; an absent or incomplete prerequisite rejects that condition.
Qualitative conditions may be supplied with a partial `WATCH` assembly.
Missing reviewed artifacts and assembly `missing_data` do not automatically
become prose conditions. Upstream `INCOMPLETE_INPUT_USED` is retained in
future plan lineage. No additional incomplete flag is added merely because a
`WATCH` plan omits monetization or exit.

## 9. Ordering, duplicates, and conflicts

All conditions normalize into one immutable tuple in this canonical order:

1. category order `monetization`, `reassessment`, `exit`; then
2. ascending `condition_id` within each category.

Caller ordering is not retained. The plan rejects duplicate condition IDs,
exact semantic duplicate quantitative conditions, exact semantic duplicate
qualitative conditions, and the same semantic trigger assigned to different
categories.

Multiple thresholds for one metric may coexist when condition IDs and
thresholds differ and each category/metric/comparison combination is valid.
For example, separately declared `2x`, `5x`, and `10x` net-liquidation
thresholds may coexist; they are not the Milestone 4 expiration thresholds
unless supplied under the distinct supported semantics.

The contract does not implement a general contradiction solver. Beyond exact
semantic duplication and invalid closed-grammar combinations, conflict
interpretation remains human judgment.

## 10. Selected record and result architecture

The selected future architecture is:

`PositionManagementPlan
PositionManagementPlanResult`

`PositionManagementPlan` conceptually retains:

`scope
candidate_id
candidate_state
as_of_date
structure
conditions`

All identity fields are deterministically copied from the exact reviewed
assembly. The caller does not separately supply them.

`PositionManagementPlanResult` conceptually retains:

`assembly_result
plan
lineage`

`assembly_result` is the exact supplied
`CandidateResearchRecordAssemblyResult`. The result does not retain separate
duplicate artifact fields. Exact final field annotations, constructor
behavior, module, exports, and producer signature remain decisions for the
rerun formal preflight.

## 11. Producer boundary

The implemented producer's required inputs are exactly:

`calculation_id
assembly_result
conditions
calculated_at`

There are no implicit values. The public function name and four-parameter
surface are frozen above.

The producer must not accept a separately supplied candidate ID, candidate
state, structure, as-of date, artifact dictionaries, seven individual
wrappers, current time, generated IDs, provider handles, or LLM input.

## 12. Audit and lineage architecture

The future result uses the existing `CalculationLineage` type. The selected
calculation identity is:

`calculation_type: position_management_plan
methodology_id: prospective-human-judgment-position-management-plan
methodology_version: v0.1`

The implementation verifies and emits these exact strings.

Future plan lineage inputs are exactly the normalized input tuple retained by
`assembly_result.lineage.inputs`. Caller or human declarations are not
normalized market-data inputs; they belong in canonical parameters.

Future plan quality flags are exactly the enum-ordered upstream union from
assembly lineage. No flag is generated solely because a condition is
qualitative, authority is caller or human, a `WATCH` plan omits a category,
the plan is prospective, or a rationale exists.

The plan calculation ID must be distinct from the assembly calculation ID,
every direct artifact calculation ID, every retained nested dependency
calculation ID, and every normalized input record ID.

`calculated_at` is explicit, timezone-aware UTC, and no earlier than the
assembly calculation time, retained dependency calculation times, or
normalized input times. No system clock is called.

## 13. Canonical parameter direction

The top-level canonical parameter map has these keys, with membership
independent of caller insertion order:

`schema_version
output_architecture
reviewed_candidate_assembly
plan
condition_rules
prohibited_behavior`

The exact schema value is:

`schema_version = "v0.1"`

The formal preflight must enumerate every nested key and fixed value before
BUILD. The map must use the existing strict tagged canonical JSON grammar and
must not contain JSON floats.

`output_architecture` discloses the plan type, result type, retained
assembly-result type, lineage type, and prospective-only semantics.

`reviewed_candidate_assembly` discloses enough complete exact state to
reconstruct and compare the retained assembly, including complete lineage and
canonical parameters. A calculation ID alone is insufficient.

`plan` discloses the fixed scope, candidate identity, state, as-of date,
structure, and complete ordered quantitative and qualitative conditions.

`condition_rules` freezes the state matrix, category order, metric grammar,
trigger grammar, comparison rules, threshold types, authority rules,
prerequisites, duplicate rules, and ordering.

`prohibited_behavior` includes the complete no-monitoring, no-execution, and
no-generation boundary.

## 14. AI boundary

V0.1 stores no AI-generated or AI-interpreted field. AI is not a condition
authority. AI may later render or explain an already validated plan in a
separate report-integration work unit, but it may not select thresholds,
select conditions, assign categories, create event facts or source
references, determine whether a trigger is met, or generate a trade
instruction.

## 15. Integration boundary

This work unit is standalone. It does not modify:

`CandidateResearchRecord
CandidateResearchRecordAssemblyResult
ScreeningDecision
screening policy
scanner
report renderer
Chinese overview
English renderer`

Future report integration may consume a separately supplied
`PositionManagementPlanResult`. The report must preserve candidate research
state, deterministic screening state, and prospective plan conditions as
separate concepts. The plan does not modify either research or screening
state. Screening and Chinese-report integration remain separate later roadmap
work after plan implementation and review.

## 16. Explicit exclusions

The work unit excludes:

- actual holdings, opened-position state, fill price, brokerage account,
  current exposure, position sizing, optimal quantity, and annual budget;
- monitoring, polling, scheduled evaluation, reminders, notifications,
  alerts, live trigger status, and automatic reassessment;
- automatic monetization, automatic exit, stop loss, take profit, trailing
  logic, order placement, order modification, order cancellation, and
  execution;
- providers, pricing production, Event Intelligence implementation,
  event-to-underlying mapping, screening, ranking, recommendation, renderer
  integration, persistence, and services; and
- a generic rule engine, plugin framework, or registry framework.

## 17. Next formal gate

This standalone implementation is complete. Screening and Chinese-report
integration remain separate later work and require a fresh formal read-only
preflight covering their exact contract, input authority, rendering behavior,
screening interaction, localization, and compatibility. No automatic
monitoring or execution work is implied, and this document does not authorize
that later implementation.
