# Deterministic Screening Policy v0.1

> **PROVISIONAL SYNTHETIC-DEVELOPMENT POLICY — NOT VALIDATED MARKET RULES**
>
> Every threshold in this document is provisional and exists only to develop and test deterministic behavior with synthetic fixtures. The thresholds have not been calibrated from historical returns and must not be interpreted as validated market rules. This policy is not investment advice. External market data must not be connected until the policy has been tested against multiple purpose-built synthetic fixtures.

## 1. Policy purpose

The policy answers:

> Under explicit and reproducible rules, should a candidate structure be proposed as Reject, Data insufficient, Watch, or Investigate?

The policy searches for potentially cheap positive convexity rather than market direction. It evaluates a concrete option structure, not only an underlying, using supplied typed structured records.

The policy does not price options, generate market data, generate evidence, use an LLM, calculate a Convexity Score, predict returns or probabilities, recommend or execute a trade, or modify `CandidateResearchRecord`.

## 2. Planned API contract

The future evaluator is planned to expose:

```python
screen_candidate(
    candidate: CandidateResearchRecord,
    policy: ScreeningPolicy,
) -> ScreeningDecision
```

This document specifies that contract but does not implement it.

### 2.1 CandidateResearchRecord

`CandidateResearchRecord` supplies:

- the concrete option structure;
- costs;
- liquidity;
- volatility environment;
- tail-pricing slices;
- scenario results;
- classified evidence;
- disclosures and research context.

The record may already contain a human-supplied or fixture-supplied `state` and `state_rationale`. The evaluator must ignore that supplied state when calculating its deterministic decision. It must never mutate the record or overwrite the supplied state. It returns a separate `ScreeningDecision`.

### ScreeningDecision and CandidateResearchRecord remain separate

`CandidateResearchRecord.state` and `state_rationale` are supplied research-record fields. `ScreeningDecision.proposed_state` is an independently calculated deterministic result. Policy v0.1 must carry them as separate objects: the evaluator must not mutate the candidate or create a replacement `CandidateResearchRecord` merely by copying `proposed_state` into `state`.

Purpose-built screening fixtures may use any valid supplied candidate state, commonly `WATCH`; the evaluator must still produce its result independently. A future report may display both:

- the supplied research-record state;
- the deterministic proposed state.

The values must be clearly labeled and must not be silently merged. Before any future design makes the deterministic proposed state the canonical `CandidateResearchRecord.state`, the aggregate validation contract must be explicitly reviewed, including the current `INVESTIGATE` validation requirement for supporting empirical `ClassifiedEvidence`.

This is an integration constraint, not a change to policy thresholds, precedence, or state results. This task does not modify `CandidateResearchRecord`.

### 2.2 ScreeningPolicy

`ScreeningPolicy` will contain:

- `policy_id`;
- `policy_version`;
- all numerical thresholds;
- required scenario definitions;
- comparison tolerances;
- canonical reason-code ordering.

### 2.3 ScreeningDecision

`ScreeningDecision` is planned to contain:

```text
proposed_state: CandidateState
reason_codes: Tuple[ScreeningReasonCode, ...]
policy_id: str
policy_version: str
```

It must not contain a numerical score, estimated probability, expected return, candidate ranking, position sizing, or buy or sell instructions.

The decision is reproducible only when evaluated together with the immutable policy version and the unchanged candidate record.

## 3. Policy identity

```text
policy_id = synthetic-screening-v0.1
policy_version = 0.1
```

`policy_id` identifies the policy family. `policy_version` identifies an immutable rule set. Together, policy ID and version must uniquely determine:

- every threshold;
- every operator;
- every required scenario;
- scenario-matching tolerances;
- decision precedence;
- reason-code values;
- canonical reason-code ordering.

Once a policy version has been used to produce a `ScreeningDecision`, it must never be edited in place. Changing any decision-affecting rule requires a new policy version. Documentation-only wording changes that do not affect behavior may retain the same version. The future `ScreeningPolicy` object should be immutable.

## 4. Derived metrics

### 4.1 Holding-period Theta burden

```text
absolute_theta_burden =
    abs(theta_per_day) × expected_holding_days

theta_burden_percentage =
    absolute_theta_burden ÷ quoted_mid_premium
```

`theta_per_day` is the supplied total-position daily Theta. This calculation is a simple linear approximation and does not assume that real Theta remains constant. It is used only as a transparent development metric.

### 4.2 Structure-expiration tail slice

The relevant `TailPricingSlice` is the slice whose expiration equals the candidate structure expiration. Other expirations may provide term-structure context but cannot replace the structure-expiration slice.

### 4.3 Classified evidence and deterministic state

`ClassifiedEvidence` is not ignored by the product. It remains essential for report explanation, provenance, auditability, separating observed facts and calculated metrics from assumptions and AI interpretations, and supporting human review.

It is not an independent market-data input, however. Policy v0.1 must not determine deterministic state from whether a human, fixture, LLM, or upstream component classified an evidence statement as `SUPPORTS`. Absence of an optional `ClassifiedEvidence` category does not produce `DATA_INSUFFICIENT`. This documentation task does not change `CandidateResearchRecord` or its existing validation rules.

## 5. Provisional thresholds

All percentages use decimal representation internally. For example, `5.00% = 0.05`.

Every threshold below is a synthetic-development assumption, not an empirically calibrated definition of an attractive option structure or cheap tail pricing.

| Rule group | Structure | Metric | Operator | Threshold | Consequence when condition passes |
| --- | --- | --- | :---: | ---: | --- |
| Hard rejection | All | Maximum loss percentage | `>` | 5.00% | Reject |
| Hard rejection | All | Cumulative repeated-bet percentage | `>` | 15.00% | Reject |
| Hard rejection | All | Bid-ask spread percentage | `>` | 12.00% | Reject |
| Hard rejection | All | Minimum leg open interest | `<` | 50 | Reject |
| Hard rejection | All | Minimum leg daily volume | `<` | 10 | Reject |
| Hard rejection | All | Holding-period Theta burden percentage | `>` | 50.00% | Reject |
| Investigate affordability | All | Maximum loss percentage | `<=` | 2.50% | Pass affordability gate |
| Investigate affordability | All | Cumulative repeated-bet percentage | `<=` | 8.00% | Pass affordability gate |
| Investigate affordability | All | Holding-period Theta burden percentage | `<=` | 25.00% | Pass affordability gate |
| Investigate liquidity | All | Bid-ask spread percentage | `<=` | 6.00% | Pass liquidity gate |
| Investigate liquidity | All | Minimum leg open interest | `>=` | 200 | Pass liquidity gate |
| Investigate liquidity | All | Minimum leg daily volume | `>=` | 50 | Pass liquidity gate |
| Volatility support | All | IV percentile | `<=` | 40.00% | One supportive signal |
| Volatility support | All | ATM IV minus historical median ATM IV | `<=` | 0.00 percentage points | One supportive signal |
| Volatility support | All | Implied-realized volatility gap | `<=` | 0.00 percentage points | One supportive signal |
| Tail-pricing support | `long_call` | Upside 25-delta skew | `<=` | 1.50 percentage points | Required for tail support |
| Tail-pricing support | `long_call` | Upside wing curvature | `<=` | 2.50 percentage points | Required for tail support |
| Tail-pricing support | `long_put` | Downside 25-delta skew | `<=` | 2.50 percentage points | Required for tail support |
| Tail-pricing support | `long_put` | Downside wing curvature | `<=` | 3.50 percentage points | Required for tail support |

### 5.1 Hard rejection thresholds

Crossing any available hard threshold creates a conclusive rejection reason.

### 5.2 Investigate affordability gates

A candidate passes the affordability gates only when all three affordability conditions in the threshold table pass.

### 5.3 Investigate liquidity gates

A candidate passes the liquidity gates only when all three liquidity conditions in the threshold table pass.

### 5.4 Volatility-environment support

The policy evaluates three independent volatility signals: IV percentile is 40.00% or less; ATM IV minus historical median ATM IV is 0.00 percentage points or less; and the implied-realized volatility gap is 0.00 percentage points or less. The third signal passes only when ATM implied volatility is no greater than matched-horizon realized volatility.

A positive implied-realized gap means implied volatility exceeds matched recent realized volatility and therefore must not independently count as evidence that volatility is cheaply priced. A small positive gap may coexist with the other supportive signals. The volatility environment remains supportive when at least two of the three signals pass. Failure of the implied-realized signal, or failure of overall volatility support, is not a hard rejection. When the record is otherwise complete, failure of the overall support test is a soft gate leading to Watch.

### 5.5 Tail-pricing support

Tail-pricing support uses the structure-expiration slice. A `long_call` must pass both call-side conditions in the threshold table. A `long_put` must pass both put-side conditions. A `long_straddle` must pass all four call-side and put-side conditions.

Failure is not a hard rejection. When the record is otherwise complete, failure is a soft gate leading to Watch. These values are synthetic development assumptions and are not empirically calibrated definitions of cheap tail pricing.

## 6. Treatment of skew percentile

`TailPricingSlice` currently contains one scalar `skew_percentile` while separately recording upside and downside skew measurements. The scalar does not identify which directional skew series was ranked. Therefore:

- `skew_percentile` may be displayed for context;
- it must not affect `CandidateState` in policy v0.1;
- directional percentile fields may be introduced before real-data integration.

This policy does not change `TailPricingSlice`.

## 7. Required scenarios

All policy-critical scenarios use:

```text
valuation_time = holding_horizon
```

They use the structure's declared expected holding period, the per-leg starting IVs stored in `ScenarioResult`, and the supplied `pnl_after_costs`, with no probability weighting. Future scenario matching must use `math.isclose` for floating-point underlying moves and IV shocks with these provisional comparison tolerances:

```text
rel_tol = 1e-9
abs_tol = 1e-12
```

| Structure | Scenario | Underlying move | Relative IV change | Valuation time | Required result |
| --- | --- | ---: | ---: | --- | --- |
| `long_call` | Target move | +10.00% | 0.00% | `holding_horizon` | `pnl_after_costs > 0` |
| `long_call` | Volatility crush | 0.00% | -20.00% | `holding_horizon` | Disclosure only; profit not required |
| `long_put` | Target move | -10.00% | 0.00% | `holding_horizon` | `pnl_after_costs > 0` |
| `long_put` | Volatility crush | 0.00% | -20.00% | `holding_horizon` | Disclosure only; profit not required |
| `long_straddle` | Downside target | -10.00% | 0.00% | `holding_horizon` | `pnl_after_costs > 0` |
| `long_straddle` | Upside target | +10.00% | 0.00% | `holding_horizon` | `pnl_after_costs > 0` |
| `long_straddle` | Volatility crush | 0.00% | -20.00% | `holding_horizon` | Disclosure only; profit not required |

The volatility-crush scenario discloses adverse decay and volatility-contraction exposure. It does not need to be profitable.

For a long straddle, both target scenarios must be profitable after costs. Both sides use the same valuation time and IV shock so the comparison is symmetric.

A long straddle has two required target scenarios. If either supplied target scenario has `pnl_after_costs <= 0`, the decision includes `target_move_scenario_not_profitable`. That reason code appears only once even if both target scenarios fail. A missing downside or upside target uses `missing_target_move_scenario`; one instance of that code is sufficient when either or both sides are absent. The implementation must still evaluate the downside and upside scenarios separately internally. Side-specific diagnostics may be exposed later without changing the stable policy v0.1 state reason code.

Immediate and expiration scenarios may remain in reports but are not mandatory policy inputs in v0.1.

## 8. Policy-critical required data

The following inputs are decision-critical:

- `StructureCosts`;
- `StructureLiquidity`;
- `VolatilityEnvironment`;
- the structure-expiration `TailPricingSlice`;
- every required structure-specific target scenario;
- the required volatility-crush scenario.

`CandidateResearchRecord.missing_data` is disclosure text. A non-empty `missing_data` tuple does not automatically force `DATA_INSUFFICIENT`. Only absence of policy-critical structured inputs produces `DATA_INSUFFICIENT`. Absence of optional `ClassifiedEvidence` categories must not produce `DATA_INSUFFICIENT`.

## 9. Decision precedence

The evaluator applies these steps in exact order.

### Step 1 — Reject

Evaluate every hard rejection rule that can be evaluated from supplied data. Also evaluate required target scenarios that are present.

Return `REJECT` when:

- one or more hard rejection thresholds fail; or
- a required target scenario exists but has `pnl_after_costs <= 0`.

Return all applicable rejection reason codes in canonical order. A conclusive known rejection takes precedence over missing unrelated inputs. For example, if maximum loss is 8.00% but volatility evidence is absent, return Reject rather than Data insufficient.

### Step 2 — Data insufficient

When no rejection condition exists, check all policy-critical inputs. Return `DATA_INSUFFICIENT` when one or more required records or scenarios are absent. Return all applicable missing-data reason codes in canonical order.

### Step 3 — Investigate

Return `INVESTIGATE` only when:

- no rejection condition exists;
- no policy-critical input is missing;
- every affordability gate passes;
- every liquidity gate passes;
- the volatility environment is supportive;
- structure-relevant tail pricing is supportive;
- every required target scenario is profitable after costs.

Investigate means only:

> The candidate is sufficiently complete and supportive to deserve deeper human research.

It does not mean the option is cheap, the pricing is correct, expected return is positive, or the candidate should be traded.

### Step 4 — Watch

Return `WATCH` when there is no rejection, policy-critical data is complete, and one or more soft Investigate gates fail. Watch is the fallback for complete but mixed or insufficiently supportive evidence.

## 10. Exact reason codes

The future enum is named `ScreeningReasonCode`. It uses exactly the following string values.

### 10.1 Reject reasons

```text
max_loss_hard_limit_exceeded
repeated_bet_hard_limit_exceeded
spread_hard_limit_exceeded
open_interest_hard_minimum_failed
daily_volume_hard_minimum_failed
theta_burden_hard_limit_exceeded
target_move_scenario_not_profitable
```

`target_move_scenario_not_profitable` applies only when the required scenario exists. Zero P&L counts as not profitable. A missing required scenario uses a missing-data reason.

### 10.2 Data-insufficient reasons

```text
missing_costs
missing_liquidity
missing_volatility_environment
missing_structure_expiration_tail_slice
missing_target_move_scenario
missing_volatility_crush_scenario
```

For long straddles, one `missing_target_move_scenario` code is sufficient even if one or both target sides are absent. The implementation must still evaluate the downside and upside scenarios separately internally. It may expose missing-side details separately later, but policy v0.1 keeps the state reason code stable.

### 10.3 Watch reasons

```text
max_loss_above_investigate_limit
repeated_bet_above_investigate_limit
spread_above_investigate_limit
open_interest_below_investigate_minimum
daily_volume_below_investigate_minimum
theta_burden_above_investigate_limit
volatility_environment_not_supportive
tail_pricing_not_supportive
```

### 10.4 Investigate reasons

```text
affordability_gates_passed
liquidity_gates_passed
volatility_environment_supportive
tail_pricing_supportive
target_move_scenarios_profitable
```

## 11. Canonical reason-code ordering

The fixed order is:

1. Reject reasons;
2. Data-insufficient reasons;
3. Watch reasons;
4. Investigate reasons.

Within each group, preserve the exact listed order from Section 10. The future implementation must never rely on set ordering, never alphabetically sort reason codes, and always return a deterministic ordered tuple.

### Final-state reason-code isolation

`ScreeningDecision.reason_codes` contains codes only from the final proposed state's group:

- `REJECT` returns only applicable Reject reasons.
- `DATA_INSUFFICIENT` returns only applicable missing-data reasons.
- `WATCH` returns only failed soft-gate Watch reasons.
- `INVESTIGATE` returns only passed-gate Investigate reasons.

Reason codes from different state groups must not be mixed in one decision. Known but lower-precedence conditions may be available later as separate diagnostics, but they are not included in `reason_codes` in policy v0.1. Canonical ordering is preserved within the selected state group.

## 12. Boundary behavior

- A value equal to a maximum threshold passes.
- A value equal to a minimum threshold passes.
- Hard maximum rejection uses strict `>`.
- Hard minimum rejection uses strict `<`.
- Investigate maximum gates use `<=`.
- Investigate minimum gates use `>=`.
- Target-scenario profitability requires strictly positive P&L.
- Zero P&L fails.
- Percentages are stored as decimal ratios; `5.00%` is stored as `0.05`.
- Scenario shock matching uses `math.isclose` with `rel_tol=1e-9` and `abs_tol=1e-12`.
- Ordinary threshold comparisons use finite stored values directly.

## 13. Relationship to the existing bilingual fixture

The current SPY bilingual fixture exists to validate rendering. Its supplied `WATCH` state is not a policy result. The future evaluator must ignore that state, and the fixture is not required to produce any specific deterministic classification.

Purpose-built Reject, Data insufficient, Watch, and Investigate fixtures will be created during implementation. The existing fixture is unchanged by this policy task.

## 14. Non-goals

Policy v0.1 does not:

- calibrate thresholds from historical returns;
- optimize thresholds;
- adapt thresholds by asset class;
- distinguish ETF rules from single-stock rules;
- model event probabilities;
- model full volatility-surface changes;
- use `skew_percentile` in classification;
- size positions;
- rank candidates;
- calculate a Convexity Score;
- interpret free-form AI text;
- verify that narrative evidence is economically correct;
- connect to market data;
- execute trades;
- address Markdown escaping.

## 15. Open calibration questions

- Should ETF and single-stock thresholds differ?
- Should liquidity minimums depend on contract premium or underlying liquidity?
- Should target moves scale with realized or implied volatility?
- Should Theta burden use a nonlinear decay model?
- Should scenario requirements include multiple IV shocks?
- How should separate upside and downside skew percentiles be represented?
- How should thresholds be calibrated and backtested without look-ahead bias or data leakage?
- How should repeated-bet affordability eventually be connected to portfolio-level barbell allocation?
