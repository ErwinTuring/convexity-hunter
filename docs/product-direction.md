# Convexity Hunter Product Direction

This document is the canonical product direction after Milestone 3. It defines
the active product objective and roadmap without changing the completed
Milestone 1–5 implementation.

## 1. Product objective

Convexity Hunter starts from changes in the world, identifies events that may
alter future return distributions, identifies potentially affected
underlyings, uses real option-chain data to construct actual Long Option
Position candidates, lets the user select one exact option structure, and then
uses auditable market evidence to determine whether its positive convexity may
be insufficiently priced and whether its maximum loss fits the user's
explicitly declared risk assumptions.

The system identifies structures worthy of further investigation. It does not
prove that an opportunity exists, recommend a trade, or execute one. The final
unit of research is one exact option structure, not a generic asset or a
multi-position optimized portfolio.

## 2. Supported research unit and scope

`Long Option Position`, `option long position`, `期权多头仓位`, and
`买入期权结构` describe position direction. Do not use “长期权” as a synonym:
it may be confused with a Long-Term Option or LEAPS.

The active MVP supports exactly:

- Long Call;
- Long Put; and
- Long Straddle: one long call and one long put with the same underlying,
  strike, and expiration.

Each selected structure records the underlying, structure type, side of every
leg, strike, expiration, quantity, and contract multiplier. Candidate
discovery uses one standard structure unit unless the user supplies another
quantity.

The MVP excludes short options, option selling, spreads, multi-expiration
structures, exotics, 0DTE, Weeklies, portfolio optimization, automatic
execution, probability forecasts, trade recommendations, and calculation of
an optimal contract count.

## 3. Two entry paths

Discovery entry:

```text
world events
    -> Event Intelligence
    -> potentially affected underlyings
    -> distribution-change hypotheses
    -> real option-chain retrieval
    -> actual eligible option structures
    -> user selects one exact structure
    -> Convexity Engine research
```

Direct user entry:

```text
user supplies an option structure to investigate
    -> resolve and validate the real listed contract
    -> apply the same market-data, eligibility, evidence, and scope checks
    -> Convexity Engine research
```

Direct entry does not require an Event Intelligence hypothesis. It never
bypasses real contract existence, option-chain verification, supported
structure grammar, DTE policy, quote and reference-data validation,
market-data provenance, or calculation lineage. An incomplete description may
be resolved against the actual chain, but the system must never invent a
contract. Both paths converge on one verified exact `OptionStructure`.

## 4. Dual-engine architecture

Event Intelligence is the hypothesis engine. It identifies events,
potentially affected underlyings, impact paths, distribution-change
hypotheses, expected event windows, supporting and contradictory sources, and
uncertainty.

Event-to-underlying mapping is Skill-led. Convexity Hunter owns the standard
accepted result and minimum audit boundary: underlying identity resolution;
event and observation time; source retention; fact-versus-inference
separation; disclosed impact path, distribution hypothesis, and event window;
uncertainty and conflicts; Skill identity and version; and incomplete-result
handling. This is an acceptance interface, not a second mapping algorithm. Its
detailed provider-neutral contract is implemented in
[`event-intelligence-acceptance-contract.md`](event-intelligence-acceptance-contract.md)
after the bounded capability review in
[`event-intelligence-capability-research.md`](event-intelligence-capability-research.md).
It accepts only auditable hypothesis submissions and does not perform mapping,
ranking, market-data validation, or candidate generation.

A market-data and deterministic-rules component retrieves the real option
chain, confirms listed contracts, applies maturity and future strike-or-Delta
policies, constructs exact supported candidates, verifies required quote, IV,
Greeks, volume, open-interest, and reference evidence, and rejects nonexistent
or invalid structures. Language-model reasoning cannot replace the chain.

The Convexity Engine researches the exact selected structure using auditable
numerical market evidence. It does not discover contracts, make the user's
selection, or decide a trade.

## 5. Skill reuse and adapter strategy

Event Intelligence should preferentially reuse mature Skills to reduce
implementation cost and improve delivery speed. A third-party Skill may,
however, satisfy only part of the product contract.

The boundary has three layers:

1. Skill-native output is fixed by the Skill and is not arbitrarily changed by
   Convexity Hunter.
2. Adapter and Skill composition provide thin conversion, enrichment, or
   combination where necessary.
3. Convexity Hunter standard accepted input is the normalized
   event-to-underlying hypothesis contract required by the product.

A mature Skill may be used directly, wrapped by a thin adapter, combined with
another Skill, rejected as insufficient, or supplemented by narrowly scoped
internal development. Capability research must precede that decision.

AI, search, and knowledge Skills may provide event identity, summary,
observation time, source references, potentially affected underlying, impact
path, distribution-change hypothesis, expected event window, supporting and
contradictory evidence, uncertainties, and Skill identity and version. These
are hypotheses and interpreted evidence. They may not invent option prices,
strikes, expirations, listed contracts, implied volatility, Greeks, historical
observations, scenario values, or probabilities.

## 6. Candidate qualification and layered selection

Eligibility, not arbitrary absolute counts, controls candidate inclusion. An
underlying may enter structure generation only when the future accepted
contract establishes a supported US-listed equity or ETF identity, a specific
event-impact path and future distribution-change hypothesis, source-backed
mapping, a usable event window, an eligible listed option market, and
resolvable identity and chronology.

A structure may enter only when the contract exists, the structure is
supported, maturity is eligible, required quote and reference evidence is
available, and the structure is compatible with the declared distribution
hypothesis.

Information volume is controlled through layered interaction:

```text
event
    -> eligible affected underlyings
    -> user opens or selects one underlying
    -> eligible exact option structures
    -> user selects one exact structure
```

The system does not rank structures by investment attractiveness. Stable
presentation ordering is permitted but is not a recommendation.

## 7. Maturity policy

The initial versioned MVP policy permits standard monthly options only:

- hard lower bound: 30 calendar DTE;
- non-core short range: 30–59 calendar DTE;
- core hunting range: 60–120 calendar DTE;
- non-core long range: 121–150 calendar DTE;
- hard upper bound: 150 calendar DTE; and
- expiration date must be at least the expected event-window end date plus 30
  calendar days.

0DTE and Weeklies are excluded. The event buffer is an initial policy
assumption. The DTE ranges are Convexity Hunter product choices, not a fixed
universal Taleb rule. They must be versioned and may change through evidence
and backtesting. The exact definition of “standard monthly option” remains for
the future structure-generation contract.

### 7.1 Mode-based Strike and Delta generation

Discovery generation uses the declared distribution-change mode rather than
one universal Strike or Delta range:

1. **Extreme-tail mode** applies to a specific one-sided extreme downside or
   upside hypothesis. Signed option Delta is preserved as evidence; absolute
   Delta qualifies the range. The initial primary tier is
   `0.05 <= abs(delta) <= 0.10`. The fallback tier is
   `0.10 < abs(delta) <= 0.15` and is used only when the primary tier cannot
   provide an eligible real listed contract with sufficient required market
   evidence. The exploratory far-tail tier is
   `0.02 <= abs(delta) < 0.05`; it is not generated by default and requires a
   real listed contract, valid two-sided quote, usable liquidity evidence,
   available IV and reference evidence, calculable total entry cost, and
   responsible scenario valuation. Absolute Delta above 0.15 is outside this
   default grammar, not globally prohibited.
2. **Event-directional convexity mode** applies when an event creates a
   meaningful directional tail hypothesis that need not be a systemic or
   extreme-market crash. Representative targets remain approximately 10
   Delta—a farther tail with lower absolute premium, a potentially higher
   value multiple, and a larger required move—and approximately 25 Delta—a
   less remote event-sensitive structure with usually higher absolute cost
   that may respond earlier to a material event move. Neither target is
   preferred or ranked. A 25 Delta structure remains a possible candidate,
   tail-pricing comparison point, and wing-curvature evidence anchor.
3. **Bidirectional distribution-expansion mode** applies when direction is
   unresolved but the future return distribution may widen. The active MVP
   uses an ATM or near-ATM Long Straddle because it does not support Long
   Strangle.

Future deterministic generation contracts must define the Delta convention,
nearest-eligible-Delta resolution, tie handling, expiration interaction,
mode-specific quote and liquidity qualification, and the exact disclosed ATM
reference. This policy does not freeze those implementation choices, and
structure generation is not yet implemented.

The ranges govern discovery generation. A supported real structure supplied
through direct user entry is not rejected solely for falling outside them. It
still must pass real-contract verification, supported Long Option Position
grammar, DTE policy, quote and reference validation, market-data provenance,
calculation lineage, liquidity and cost analysis, and Convexity Engine
research. The report may disclose that it does not match a default discovery
mode.

Delta is not a fixed percentage distance from spot. It depends on disclosed
inputs and methodology, including underlying price, strike, remaining
maturity, implied volatility, rates, dividends, surface shape, and pricing
convention. Every generated structure must disclose its actual strike
distance separately.

Low dollar premium is not relatively cheap tail pricing. Deep OTM options may
carry expensive tail IV, wide spreads, poor liquidity, or model-sensitive
values. Initial far-OTM Gamma is commonly low and can increase as the option
moves toward ATM; tail-event value may reflect price movement, IV repricing,
skew or surface repricing, and changing Greeks. No universal claim of high
initial Gamma or maximum Vega applies, and Vanna or Volga are not required MVP
fields.

## 8. Three-layer Convexity Engine

Layer 1 asks whether the overall option-pricing environment is relatively
quiet or expensive. It includes ATM IV percentile, ATM IV relative to its
historical median, IV term structure, and the matched-horizon
implied-versus-realized volatility gap.

Layer 2 asks which tail, if any, appears relatively cheap against ATM and its
own history. It includes 25-delta put IV minus ATM IV, 25-delta call IV minus
ATM IV, 10-delta versus 25-delta wing curvature, current skew percentile, and
skew term structure.

Layer 3 asks whether the exact structure is a bearable and sufficiently
nonlinear way to own the hypothesized convexity after costs. It includes the
real price, spread, commissions and fees, total entry cost, maximum loss,
Theta, raw total-position Gamma, local Gamma-cost relationship,
repeated-failure cost, scenario values, expiration value thresholds,
portfolio-relative loss, and risk-budget assessment.

Positive convexity does not establish cheapness. A Long Option Position can be
positively convex yet too expensive, illiquid, rapidly decaying, or
inconsistent with the hypothesis. Detailed numerical contracts live in
[the market-data specification](market-data-contracts.md) and deterministic
decision rules in [the screening policy](screening-policy.md).

## 9. Expiration payoff-threshold evidence

The implemented deterministic expiration transformation uses:

```text
expiration position-value multiple =
    expiration gross position value / total entry cost
```

The exact ordered target set is 1x, 2x, 5x, and 10x. At 1x, expiration gross
position value equals total entry cost: break-even before any separately
disclosed expiration exit cost. Total entry cost includes total-position
midpoint premium, one-way entry spread cost, commissions, and fees. Exit cost
is excluded from the threshold equation.

The transformation supports Long Call, Long Put, and the current same-strike,
same-expiration, same-quantity, same-multiplier Long Straddle. It returns the
structure-appropriate single or double payoff branches and explicitly
represents a lower-side solution that is unavailable on the nonnegative
underlying-price domain.

Every available threshold includes a signed absolute USD-per-share move and a
signed relative move from the reviewed base underlying price. A percentage is
a later presentation derivation from the relative move. Side identifies the
payoff branch and does not necessarily equal the sign of the move from the
current base price. “Exact” means mathematically exact rational evidence, not
a rounded `Decimal` or float approximation.

The implemented transformation produces expiration payoff-threshold evidence
only. It
calculates no probability, expected return, direction forecast,
recommendation, position sizing, automatic exit advice, or screening or
report consequence. Candidate assembly, screening, reporting integration, and
services remain separate layers; this transformation does not perform them.
The completed downstream position-management integration consumes a separately
verified result at the renderer boundary. The complete
public artifact, exact mathematics, validation, lineage, and export contract
is frozen in
[Milestone 4 of the market-data specification](market-data-contracts.md#1323-milestone-4-deterministic-expiration-payoff-threshold-evidence).

## 10. Non-expiration scenarios

Non-expiration scenario value asks what the structure might be worth at an
intermediate valuation time if underlying price, implied volatility, remaining
time, rates, dividends, and the volatility surface change. It captures price
movement, IV repricing, remaining time value, Theta decay, IV-collapse risk,
and potential pre-expiration liquidation value.

Expiration thresholds show terminal payoff shape and tail-value steepness;
non-expiration scenarios show possible value while time and volatility value
remain. The repository currently validates and consumes authoritative
non-expiration scenario-pricing evidence but does not produce those prices.
A future milestone must select and disclose an external provider, an internal
pricing model, or both.

The existing general v0.1 scenario grid remains the current implemented
baseline. Future extreme-tail generation must add directionally aligned
event-level, severe, and extreme-tail stress rather than relying only on
ordinary ±5% or ±10% moves. Exact shocks must be versioned and may differ for
an index, ETF, lower- or higher-volatility equity, or event type; there is no
universal ±30% scenario.

Every IV shock must disclose base IV, shocked IV, and whether the change is a
relative percentage or absolute volatility-point change. Current v0.1
proportional IV scenarios retain their implemented semantics. Future
mode-specific contracts may add disclosed surface and skew changes.

A large value multiple under an extreme scenario is important evidence, but
no single multiple—including 50x—automatically determines `Investigate`.
Screening continues to use the complete applicable evidence boundary,
including volatility environment, tail-relative pricing, liquidity, cost,
affordability or `Data insufficient`, scenario coverage, expiration
thresholds, and evidence quality.

## 11. Risk-budget assumptions

Discovery and generation do not require portfolio value or a risk budget.
For one already-specified supported long option structure, the implemented
Milestone 5 standalone affordability assessment accepts an exact caller
portfolio-value assumption and requires two separate fractional boundaries for
a conclusive result:

1. maximum loss fraction for the single already-specified structure; and
2. maximum cumulative loss fraction for the dependency's declared equal
   repeated-attempt scenario.

The reviewed repeated-bet count comes only from the authoritative
`StructureCosts` v0.2 dependency. Equal repeated attempts do not represent
concurrent portfolio exposure, annual trading frequency, an annual
tail-protection budget, expected occurrence count, or full portfolio holdings.

Using exact lineage values rather than public floats, the assessment
calculates:

```text
single-loss fraction = maximum loss / exact portfolio value
repeated-loss fraction =
    maximum loss * repeated-bet count / exact portfolio value
```

The three outcomes are `affordable`, `not_affordable`, and
`data_insufficient`. Portfolio value, both fractional boundaries, and a
risk-budget methodology are mandatory for a conclusive outcome. If any is
missing, the result is `data_insufficient`, contains every applicable
missing-assumption reason in canonical order, and does not evaluate boundary
breaches. Loss fractions remain available when portfolio value is present.
Equality with both boundaries is affordable.

The product imposes no universal risk percentage and v0.1 has no annual
budget, absolute USD budget, inverse sizing, maximum affordable quantity,
holdings or committed-exposure model, screening action, candidate assembly, or
report integration. Existing synthetic screening thresholds are not
caller-affordability policy. Milestone 5 implements this reviewed standalone
evidence separately from candidate assembly, screening, reporting, sizing,
holdings, monitoring, and execution; see
[Risk-Assessment Contracts](risk-assessment-contracts.md).

## 12. Position-management plan contract

The canonical product and architecture clarification is
[Position-Management Plan Contract](position-management-contracts.md). The
selected artifact identity is `PositionManagementPlan`: prospective research
guidance for a hypothetical future long-option position, for later human
judgment only. Its fixed scope is `prospective_research_guidance`.

The plan is permitted only for `INVESTIGATE` and `WATCH` assemblies.
`INVESTIGATE` requires nonempty monetization, reassessment, and exit
categories. `WATCH` requires at least one reassessment condition; monetization
and exit may be empty. `REJECT` and `DATA_INSUFFICIENT` do not receive a plan.
The plan uses exactly one reviewed
`CandidateResearchRecordAssemblyResult` and does not accept separate artifact
arguments.

V0.1 is future-condition declaration only. It never evaluates current trigger
status and contains no monitoring, alerting, live position value or P&L,
current executable quote, automatic decision, or system-clock evaluation.
Categories structurally map only to “consider monetization,” “consider
reassessment,” and “consider exit”; they cannot encode a sell, close-now,
take-profit, stop-out, or execution instruction.

Conditions use closed immutable quantitative and qualitative forms. Quantitative
metrics are net liquidation value multiple, remaining DTE, bid-ask spread
fraction, ATM IV, skew percentile, single-loss fraction, and repeated-loss
fraction, with only inclusive comparisons and exact non-float thresholds.
Qualitative triggers are the closed event, evidence, contract, impact-path,
and data-loss declarations in the canonical contract. Thresholds are supplied
by the caller or human analyst except the exact reviewed M5 risk boundaries;
AI is not an authority and no event record is accepted.

The implemented architecture is `PositionManagementPlan` plus
`PositionManagementPlanResult`, retaining the exact assembly result and
existing `CalculationLineage`. It is implemented in
`src/convexity_hunter/position_management.py` with focused coverage in
`tests/test_position_management.py`; the exact records and four-parameter
producer are frozen by the canonical contract. The work unit was independently
reviewed, corrected, and passed targeted re-review. It remains unnumbered;
screening and Chinese-report integration are now complete as a separate
downstream work unit. The renderer accepts exactly
`render_candidate_markdown(candidate, locale="en", screening_decision=None,
position_management_plan_result=None)`. A supplied plan is optional, must be
verified, is rendered only for Chinese `WATCH` or `INVESTIGATE` reports, and
does not change research or screening state.

## 13. Chinese report and simplified overview

The active product flow produces a Chinese report only. The implemented
English renderer remains for compatibility and possible future reuse, but
English is inactive. Reactivation requires a separately accepted product
decision; completed bilingual implementation remains a historical fact.

The first report section is a short, ordinary-Chinese overview for users with
little option experience:

1. the exact underlying and structure in beginner-readable language;
2. the final research disposition—Investigate, Watch, Reject, or Data
   insufficient in plain Chinese—and an explicit reminder that it is research
   priority, not a buy/sell recommendation;
3. a few decisive supporting and caution reasons;
4. the main uncertainty, missing evidence, false-positive risk, or
   human-review question; and
5. concise future monetization, reassessment, and exit conditions.

When a verified plan result is supplied, the Chinese report adds future
condition declaration and technical detail sections. The renderer requires the
candidate object retained by the verified result, preserves stored condition
order, and states that conditions have not been evaluated. With no plan, the
existing English and Chinese output remains byte-compatible and no empty plan
section is added. English plan rendering is unsupported. The integration is
declaration-only and does not create, screen, monitor, alert, schedule,
recommend, or execute a position-management plan.

Necessary option terms are explained briefly. The overview contains no
unexplained jargon, long methodology, full metric/provenance tables,
uncalculated probabilities, or implied trade recommendation. Detailed
provenance, lineage, metrics, costs, risk calculations, thresholds, scenarios,
evidence, falsification, methodologies, limitations, and review questions
remain below. If supplied `CandidateResearchRecord` state differs from the
deterministic `ScreeningDecision`, one short sentence surfaces the
disagreement; details retain both exact states and reason codes.

“最终建议” means research disposition. Acceptable wording includes
“最终研究结论”, “是否值得进一步研究”, “建议继续调查”, “建议观察”,
“建议暂不继续”, and “数据不足，无法负责地判断”. It must not become a
buy/sell instruction, return claim, or probability claim.

## 14. Completed Milestones 1–3

Milestone 1 implemented `CandidateResearchRecord`, evidence classification,
supporting and contradictory evidence, falsification, false-positive reasons,
human-review questions, deterministic report rendering, and a plain-language
overview before technical detail. Bilingual rendering is a completed
historical fact.

Milestone 2 implemented `ScreeningPolicy`, `ScreeningDecision`, Reject, Watch,
Investigate, Data insufficient, canonical reason codes, deterministic
precedence, and report integration that keeps research and proposed states
separate.

Milestone 3 completed at commit
`86aee1dfa13cae0c865d8f24aa08754934abd540` (`Implement hybrid scenario
valuation transformation`). It implemented provider-neutral market-data
contracts, provenance and normalization, freshness, correction selection,
relationship coherence, cross-observation selection, historical-series
assessment, calculation lineage, structure liquidity and costs, historical
realized volatility, volatility environment, tail relative pricing, a
scenario-pricing evidence contract, and hybrid non-expiration/expiration
scenario valuation.

## 15. Current gaps

Convexity Hunter has largely completed the auditable numerical and evidence
foundation for researching one already-specified option structure. It has not
yet completed the active-discovery front end, real option-structure
generation, broader discovery/application-flow candidate production,
non-expiration pricing production, or the complete application flow. Standalone
prospective plan construction is implemented and complete under [the canonical
contract](position-management-contracts.md), and the separate downstream
screening and Chinese-report integration is also complete for optional,
verified Chinese rendering. Reviewed-artifact candidate assembly is complete:
Milestone 6A provides the prerequisite wrapper verifiability and Milestone 6B
assembles the reviewed artifacts without adding screening or reporting
behavior of its own.
The deterministic offline single-structure service is implemented and
independently reviewed under the
[canonical service contract](offline-single-structure-service-contract.md),
with exactly three direct-module public names and zero package-root exports.
Milestone 4 — Deterministic Expiration Payoff-Threshold Evidence
implements exact-rational expiration 1x/2x/5x/10x thresholds. Milestone 5 —
Standalone Structure Affordability Evidence implements reviewed standalone
affordability evidence for one already-specified supported structure. It does
not integrate candidate assembly, screening, reporting, sizing, holdings,
monitoring, or execution.

Project claims must distinguish implemented capability, implemented record or
contract, transformation requiring caller orchestration, synthetic-only
integration, and not-yet-implemented work. A domain record alone is not a
complete application workflow.

Futu OpenAPI is the preferred MVP U.S. market-data provider, with Tiger frozen
as fallback and no router or blending. One real Futu exact contract has passed
the partial Direct Entry loop through deterministic `DATA_INSUFFICIENT` and a
Chinese report without weakening missing-evidence boundaries. Provider
timestamp, exact-deliverable, activity, and Greeks gaps remain fail-closed;
they are not the current roadmap priority.

## 16. Corrected roadmap

1. Prior documentation alignment.
2. Completed Milestone 4 — Deterministic Expiration Payoff-Threshold Evidence.
3. Completed Milestone 5 — Standalone Structure Affordability Evidence.
4. Completed Milestone 6A — Reviewed Artifact Verifiability.
5. Completed Milestone 6B — Reviewed-Artifact Candidate Assembly. The initial
   zero-artifact preflight blocker was clarified and implemented; independent
   review found one accepted MAJOR direct-construction error-taxonomy defect,
   which was corrected, and targeted re-review passed with no findings.
6. Completed standalone Position-Management Plan Contract implementation. The
   work unit remains unnumbered; independent review, correction, and targeted
   re-review are complete.
7. Completed separate, unnumbered Position-Management Plan Screening and
   Chinese-Report Integration work unit.
8. Completed deterministic offline single-structure service contract,
   implementation, focused tests, and independent review.
9. Completed Tiger local runtime and bounded provider evidence work, retained
   as fallback.
10. Completed bounded Futu provider and real Direct Entry partial-loop proof.
11. Completed bounded Hunter/Event Intelligence capability research and the
    source-backed event-to-underlying acceptance contract.
12. Current: exercise the accepted boundary with one repository-external,
    source-backed real event submission before selecting any adapter.
13. Later: the smallest justified event-source adapter, discovery, exact
    structure generation, and complete-flow work only after that real exercise.

## 17. Locked principles

- Events create hypotheses; numerical market evidence tests pricing.
- AI explains and structures research but never invents numerical evidence or
  makes the trade decision.
- The user chooses one verified exact structure.
- Positive convexity is not proof of cheapness.
- Risk bearability depends on explicit user assumptions.
- Candidate qualification is rule-based and selection is layered, not
  arbitrarily capped or automatically ranked.
- Strike and Delta discovery generation is mode-based, not universal; 25 Delta
  is not globally rejected and direct entry is not bounded by discovery-mode
  defaults alone.
- Low premium does not establish cheapness, no single scenario multiple
  determines `Investigate`, and no universal annual convexity budget applies.
- The product reports research dispositions and prospective human-judgment
  conditions under the canonical position-management contract; it does not
  monitor, recommend, or execute.
- Completed Milestone 1–3 history remains unchanged.
- Futu OpenAPI is the preferred MVP U.S. market-data provider through an
  already-authenticated local OpenD instance. Tiger remains a frozen fallback
  capability. Provider credentials remain provider-native, per-user,
  local-only, runtime-resolved, and outside model context and repository state;
  no provider router or blending is authorized.
- Milestone 4 — Deterministic Expiration Payoff-Threshold Evidence is complete.
- Milestone 5 — Standalone Structure Affordability Evidence is complete.
- Milestone 6A — Reviewed Artifact Verifiability and Milestone 6B —
  Reviewed-Artifact Candidate Assembly are complete. The standalone,
  unnumbered Position-Management Plan Contract is also complete after
  correction and targeted re-review. Its separate downstream screening and
  Chinese-report integration is complete. The deterministic offline
  single-structure service is implemented and independently reviewed under its
  A-level contract, with zero package-root exports.
  The canonical Milestone 6 contract is
  [`candidate-assembly-contracts.md`](candidate-assembly-contracts.md), while
  [`position-management-contracts.md`](position-management-contracts.md) is
  the canonical plan contract. The service contract is
  [`offline-single-structure-service-contract.md`](offline-single-structure-service-contract.md).

## 18. Future design questions

The following are unresolved future contracts, not blockers for this alignment:

- the exact standard-monthly-option definition;
- event-window date representation;
- the exact Delta convention, nearest-eligible-Delta resolution, tie handling,
  and expiration interaction;
- the exact ATM or near-ATM definition;
- mode-specific quote and liquidity qualification;
- asset-class and event-specific stress calibration;
- the annual convexity-budget contract decision;
- actual mature Skills, their gaps, adapters, and compositions;
- provider versus internal non-expiration pricing;
- final event-to-underlying accepted contract;
- direct-entry resolution of incomplete structure descriptions.
