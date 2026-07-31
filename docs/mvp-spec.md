# MVP Specification

Convexity Hunter v0.1 identifies exact Long Option Position structures that
deserve further investigation as potentially underpriced positive-convexity
opportunities. It does not prove an opportunity exists, predict market
direction, issue trade recommendations, monitor positions, or execute trades.
The canonical post-Milestone-3 direction is in
[product-direction.md](product-direction.md).

## 1. MVP research question and entry modes

The system must answer:

> Which exact supported option structures deserve further investigation
> because their downside is bounded, their positive convexity may be
> insufficiently priced, and their maximum loss fits the user's explicitly
> declared risk assumptions?

The final research unit is one verified exact `OptionStructure`, not a generic
asset or a multi-position portfolio.

The MVP has two equal first-class entry modes:

1. **Discovery entry:** world events flow through Event Intelligence,
   potentially affected underlyings and distribution-change hypotheses, real
   option-chain retrieval and eligible structure generation; the user then
   selects one exact structure for Convexity Engine research.
2. **Direct user entry:** the user supplies a structure to investigate; the
   system resolves and validates the real listed contract and applies the same
   eligibility, market-data, and evidence checks before Convexity Engine
   research.

Direct entry does not require an Event Intelligence hypothesis. It does not
bypass contract existence, option-chain verification, supported grammar, DTE
policy, quote and reference-data validation, provenance, or calculation
lineage. An incomplete description may be resolved against the real chain but
must never result in an invented contract.

## 2. Supported scope and terminology

`Long Option Position`, `option long position`, `期权多头仓位`, and
`买入期权结构` refer to position direction. Do not use “长期权” as a synonym,
because it can mean a Long-Term Option or LEAPS.

MVP v0.1 is limited to:

- US-listed equities and ETFs;
- Long Call;
- Long Put;
- Long Straddle;
- one exact structure at a time with one or two long-option legs; and
- one standard structure unit unless the user explicitly supplies another
  quantity.

A Long Call or Long Put contains one leg. A Long Straddle contains one long
call and one long put with the same underlying, strike, and expiration.

The MVP excludes:

- short options and option selling;
- spreads, multi-expiration structures, and exotics;
- 0DTE and Weeklies;
- portfolio optimization and optimal-contract-count calculation;
- automatic discovery claims, monitoring, scheduled tasks, alerts,
  notifications, automatic exits, and execution;
- precise probability forecasts, expected-return forecasts, and trade
  recommendations; and
- LLM-generated numerical market data.

Positive convexity bounds maximum loss for the supported structures but does
not prove cheapness or bearability.

## 3. Candidate qualification and user selection

Candidate inclusion is determined by business and technical eligibility, not
an arbitrary maximum number of underlyings or structures.

For discovery entry, an underlying may enter generation only when the future
accepted contract establishes a supported security identity, specific
source-backed event-impact path, specific distribution-change hypothesis,
usable event window, eligible listed option market, and resolvable identity
and chronology.

A structure may enter only when the listed contract exists, its grammar and
maturity are supported, required quote and reference evidence is available,
and it is compatible with the declared distribution hypothesis.

The interaction is layered:

```text
event
    -> eligible affected underlyings
    -> user opens or selects one underlying
    -> eligible exact option structures
    -> user selects one exact structure
```

The selected object includes underlying, structure type, side of each leg,
strike, expiration, quantity, and contract multiplier. The system does not
rank structures by investment attractiveness. Stable presentation ordering is
allowed but is not a recommendation.

## 4. Initial maturity policy

The initial versioned policy accepts standard monthly options only:

- 30 calendar DTE hard lower bound;
- 30–59 calendar DTE non-core short range;
- 60–120 calendar DTE core hunting range;
- 121–150 calendar DTE non-core long range;
- 150 calendar DTE hard upper bound; and
- expiration date at least the expected event-window end date plus 30 calendar
  days.

The event buffer and DTE ranges are initial Convexity Hunter product-policy
assumptions, not fixed universal Taleb rules. They may be revised through
evidence and backtesting. The future structure-generation contract must freeze
the exact definition of “standard monthly option.”

### 4.1 Mode-based Strike and Delta generation

Discovery-generated candidates use the declared distribution-change mode:

1. **Extreme-tail mode:** for a specific one-sided extreme downside or upside
   hypothesis, preserve signed Delta as evidence and qualify by absolute
   Delta. The primary tier is `0.05 <= abs(delta) <= 0.10`. The fallback tier
   is `0.10 < abs(delta) <= 0.15` and is used only when the primary tier cannot
   provide an eligible real listed contract with sufficient required market
   evidence. The non-default exploratory far-tail tier is
   `0.02 <= abs(delta) < 0.05` and requires a real listed contract, valid
   two-sided quote, usable liquidity evidence, available IV and reference
   evidence, calculable total entry cost, and responsible scenario valuation.
   Absolute Delta above 0.15 is outside the default extreme-tail grammar, not
   globally rejected.
2. **Event-directional convexity mode:** for a meaningful directional event
   tail that is not necessarily systemic or extreme-market, retain
   representative targets near 10 Delta and 25 Delta without ranking them.
   The farther 10 Delta region generally has lower absolute premium, may offer
   a higher value multiple, and requires a larger move. The less remote 25
   Delta region usually costs more and may respond earlier to a material event
   move. A 25 Delta structure remains an eligible research candidate,
   tail-pricing comparison point, and wing-curvature evidence anchor.
3. **Bidirectional distribution-expansion mode:** when direction is unresolved
   but the future return distribution may widen, use an ATM or near-ATM Long
   Straddle. Long Strangle is outside the active MVP.

The future deterministic generation contract must define Delta convention,
nearest-eligible-Delta resolution, tie handling, expiration interaction,
mode-specific quote and liquidity qualification, and the exact ATM reference.
These implementation details are not frozen here, and structure generation is
not yet implemented.

This policy controls discovery-generated candidate eligibility. A supported
real structure supplied directly by the user is not rejected solely because
it lies outside default discovery-mode Delta ranges. Direct entry still must
pass real-contract verification, supported grammar, DTE policy, quote and
reference validation, provenance, calculation lineage, liquidity and cost
analysis, and Convexity Engine research. Its report may disclose that the
structure does not correspond to a default discovery mode.

Delta does not equal a fixed percentage distance from spot. It depends on
underlying price, strike, remaining maturity, implied volatility, rates,
dividends, surface shape, and pricing convention. Generated structures must
separately disclose actual strike distance.

Low dollar premium does not establish relatively cheap convexity. Deep OTM
options may have expensive tail IV, wide spreads, weak liquidity, or
model-sensitive values. Initial far-OTM Gamma is commonly low and may increase
as the option moves toward ATM; tail-event value can reflect price movement,
IV repricing, skew or surface repricing, and changing Greeks. There is no
universal claim of high initial Gamma or maximum Vega, and Vanna or Volga do
not become required MVP fields.

## 5. Three-layer screening model

### Layer 1: Volatility pricing environment

**Question:** Is the overall option-pricing environment relatively quiet or
expensive?

Required evidence:

- ATM implied-volatility percentile;
- ATM IV relative to its historical median;
- implied-volatility term structure; and
- matched-horizon implied-versus-realized volatility gap.

A 30-day IV must be compared with realized volatility over a comparable
horizon using a consistent annualization method. Low IV percentile is only an
investigation signal. Percentile and median calculations disclose observation
counts.

### Layer 2: Tail relative pricing

**Question:** Which tail, if any, appears relatively cheap against ATM and its
own history?

Required evidence:

- 25-delta put IV minus ATM IV;
- 25-delta call IV minus ATM IV;
- 10-delta versus 25-delta wing curvature;
- current skew percentile; and
- skew term structure.

Skew is a relative-price measure, not proof of absolute cheapness. Percentiles
disclose observation counts; 10- and 25-delta measurements disclose delta and
interpolation methodology. One historical observation is one valid US market
trading session using one end-of-day observation per session; intraday,
weekly, calendar-day, and mixed-frequency histories are outside scope.

### Layer 3: Concrete structure validation

**Question:** Is this exact structure a bearable and sufficiently nonlinear
way to own the hypothesized convexity after costs?

Each candidate includes, where applicable:

- exact structure identity and leg sides, strikes, expiration, quantities, and
  multipliers;
- real option price, total-position quoted midpoint, spread, commissions,
  fees, total entry cost, and maximum loss;
- total-position bid and ask, relative spread, weakest-leg open interest and
  volume, and quote methodology;
- total-position Theta and raw Gamma;
- local Gamma P&L approximation and Gamma-cost relationship for a 1%
  underlying move;
- repeated-failure cost;
- non-expiration scenario values and expiration 1x/2x/5x/10x value
  thresholds; and
- portfolio-relative loss and explicit risk-budget assessment.

All cost values are total-position USD values. Quoted midpoint excludes spread,
commissions, and fees. Gamma is total-position `d²V/dS²` in USD of position
value per USD² of underlying movement and already incorporates every leg,
quantity, and multiplier. Theta is total-position daily value change under a
disclosed day-count and pricing methodology.

The local Gamma approximation excludes Delta, Vega, Theta, surface changes,
jumps, and model error; it is not expected profit. Liquidity records expose
evidence but do not themselves impose sufficiency thresholds.

## 6. Expiration payoff-threshold evidence

The implemented deterministic transformation uses:

```text
expiration position-value multiple =
    expiration gross position value / total entry cost
```

The exact ordered target set is 1x, 2x, 5x, and 10x. For Long Call, Long Put,
and the current same-strike, same-expiration, same-quantity, same-multiplier
Long Straddle, it determines the exact expiration underlying price or prices
required for:

- 1x: expiration gross position value equals total entry cost, or break-even
  before any
  separately disclosed expiration exit cost;
- 2x: expiration gross position value equals two times total entry cost;
- 5x: expiration gross position value equals five times total entry cost; and
- 10x: expiration gross position value equals ten times total entry cost.

Total entry cost includes total-position midpoint premium, one-way entry
spread cost, commissions, and fees. Exit cost is excluded from the threshold
equation. The transformation returns the structure-appropriate single or
double payoff branches and explicitly represents a lower-side solution that
is unavailable on the nonnegative underlying-price domain.

“Exact” means mathematically exact rational evidence, not a rounded `Decimal`
or float approximation. Every available threshold contains a signed absolute
USD-per-share move and signed relative move from the reviewed base underlying
price; a percentage is a later presentation derivation from the relative
move. Side identifies the payoff branch and does not necessarily equal the
sign of the move from the current base price.

The implemented transformation produces evidence only. It calculates no
probability, expected return, direction forecast, recommendation, position
sizing, automatic exit advice, or screening or report consequence. Candidate
assembly, screening and report integration, position-management integration,
and services remain later work. The complete technical contract is
[Milestone 4 deterministic expiration payoff-threshold evidence](market-data-contracts.md#1323-milestone-4-deterministic-expiration-payoff-threshold-evidence).

## 7. Non-expiration scenario framework

Non-expiration scenario value asks what a structure might be worth at an
intermediate valuation time after changes in underlying price, implied
volatility, remaining time, rates, dividends, and the volatility surface. It
captures price movement, IV repricing, remaining time value, Theta decay,
IV-collapse risk, and potential pre-expiration liquidation value.

Expiration thresholds describe terminal payoff shape; non-expiration scenarios
describe possible value while time and volatility value remain. The repository
currently validates and consumes authoritative non-expiration scenario-pricing
evidence but does not produce the prices. A future milestone must choose and
disclose a provider, internal pricing model, or both.

Every scenario result identifies valuation time. Initial valuation-time
scenarios are immediate shock, 7 calendar days later, the declared expected
holding horizon, and expiration. A report may use a relevant subset but cannot
omit valuation time or remaining-time effects.

Initial price shocks are -20%, -10%, -5%, 0%, +5%, +10%, and +20%. Initial IV
shocks are -20%, unchanged, +20%, and +50%, interpreted as relative changes to
each leg's actual base IV. This parallel proportional shock does not model
skew, smile-curvature, or term-structure-shape changes.

Each scenario records base and shocked underlying price, leg-level base and
shocked IV, valuation date, total-position value, entry-cost basis, exit cost,
after-cost P&L, and pricing methodology. Methodology discloses provider or
model, rates, dividends, surface construction, interpolation, and limitations.
At expiration, IV inputs remain for auditability even though terminal payoff
does not depend on them.

For supported long-only structures, net liquidation value is floored at zero:
if exit cost exceeds position value, rational abandonment is assumed.
Scenario P&L therefore cannot be worse than negative entry cost.

This general grid remains the current implemented baseline. Future
extreme-tail generation requires directionally aligned event-level, severe,
and extreme-tail stress rather than only ordinary ±5% or ±10% moves. Exact
shock levels must be versioned and may vary by index, ETF, lower- or
higher-volatility equity, or event type; no universal ±30% shock is frozen.

IV shocks must disclose base and shocked values and whether the change is a
relative percentage or an absolute volatility-point change. The v0.1
proportional IV semantics remain current. Future mode-specific contracts may
add surface and skew shocks with disclosed methodology.

A large scenario value multiple is evidence, not a sole state rule. No 50x
requirement or any other single scenario multiple automatically determines
`Investigate`; the complete three-layer evidence boundary continues to apply.

## 8. Risk-budget and affordability behavior

Discovery and generation do not require portfolio value or a risk budget.
The implemented v0.1 `convexity_hunter.risk_assessment` module produces
standalone, auditable affordability evidence for one already-specified
supported long option structure. This capability remains separate from
candidate assembly, screening, reporting, and sizing. A conclusive result
requires an exact caller portfolio-value
assumption, a maximum single-structure loss fraction, a maximum repeated-loss
fraction, and a risk-budget methodology. Both boundaries are fractions in the
inclusive range `[0, 1]`.

The repeated-bet count is not a caller risk assumption. It comes only from the
reviewed `StructureCosts` v0.2 dependency and represents equal repeated
attempts, not concurrent exposure, annual frequency, expected occurrence
count, an annual budget, or portfolio holdings.

Using the dependency's exact maximum loss rather than its public floats, the
assessment calculates:

```text
single-loss fraction = exact maximum loss / exact portfolio value
repeated-loss fraction =
    exact maximum loss * repeated-bet count / exact portfolio value
```

The outcome is `affordable` only when both actual fractions are less than or
equal to their boundaries, `not_affordable` when either complete comparison
exceeds its boundary, and `data_insufficient` when any required assumption is
missing. Missing-assumption reasons take precedence over breach evaluation.
If portfolio value is present, actual fractions remain available even for an
incomplete result; otherwise they are absent.

v0.1 imposes no universal portfolio-risk percentage and has no annual or
absolute USD budget, budget utilization, remaining budget, quantity or
maximum-affordable-quantity calculation, holdings or committed-exposure
model, trade recommendation, screening state, candidate assembly, or report
integration. Candidate-state and screening semantics are unchanged. See the
canonical [Risk-Assessment Contracts](risk-assessment-contracts.md).

## 9. Candidate states

The MVP uses no unsupported numerical Convexity Score. It uses four research
states:

- **Reject:** the structure fails a required bounded-loss, affordability,
  liquidity, convexity, or cost test;
- **Watch:** some evidence is interesting, but the structure is not currently
  attractive or evidence is incomplete;
- **Investigate:** the structure passes the initial three-layer screen and
  deserves deeper human research; and
- **Data insufficient:** required evidence is unavailable or unreliable, so
  responsible screening is impossible.

These are research dispositions, not investment recommendations.

## 10. Evidence and falsification

Every output separates:

- **Observed fact:** sourced market or reference data;
- **Calculated metric:** reproducible output derived from observations;
- **Assumption:** a declared non-observed input; and
- **AI interpretation:** explanation, critique, or hypothesis.

AI may explain and critique evidence but may not invent prices, contracts,
strikes, expirations, implied volatility, Greeks, historical values, scenario
values, or probabilities.

Every investigation candidate identifies supporting and weakening evidence,
falsification conditions, missing data, false-positive reasons, and
human-review questions.

## 11. CandidateResearchRecord and screening

`CandidateResearchRecord` is the canonical aggregate for one already-specified
candidate structure. It stores a supplied `CandidateState` and rationale but
does not derive the state. It enforces structure, underlying, date,
expiration, entry-cost, underlying-price, and quoted-midpoint consistency and
separates evidence by kind and impact.

Watch, Reject, and Data insufficient records may remain incomplete if missing
data is disclosed. Investigate requires three-layer completeness and at least
one supporting observed fact or calculated metric; assumptions and AI
interpretations cannot provide empirical support alone. A domain record does
not constitute a complete application workflow.

A report may receive a separately calculated `ScreeningDecision`. It must keep
the supplied research-record state separate from the deterministic proposed
state, preserve policy identity and canonical reason-code order, surface any
disagreement, and never mutate or silently merge the record. If no decision is
supplied, the report says so rather than screening automatically.

## 12. First-report position-management conditions

The first report states in advance:

- monetization conditions under which initially underpriced convexity may have
  repriced;
- reassessment conditions that require fresh analysis;
- exit conditions that may invalidate or make the position irresponsible to
  evaluate; and
- limitations.

Conditions should be quantitative where evidence permits. Examples include
disclosed executable 2x/5x/10x liquidation multiples; ATM IV and skew
thresholds; event publication; disappearance of underpricing evidence; a
disclosed event-window change; loss of the event buffer; DTE reaching 30 days;
a disclosed spread threshold; stale data or a contract adjustment; event
cancellation or contrary resolution; invalidated impact path; a user
risk-budget breach; insufficient liquidity; or loss of required evidence.

There is no universal automatic 2x take-profit or option-price drawdown stop.
A price decline alone does not invalidate a hypothesis when predefined maximum
loss remains within the user's declared risk budget. The report says “consider
monetization,” “consider reassessment,” or “consider exit”; it does not issue
mandatory buy or sell instructions.

The MVP does not monitor positions, schedule tasks, send alerts or
notifications, or automate exits. The final position-management record,
condition ownership, threshold derivation, and report integration require a
future preflight; this specification does not freeze a class signature.

## 13. Active Chinese report

The active user-facing output is Chinese only. The implemented English
renderer remains in the repository for compatibility and possible future
reuse, but it is not part of the active product flow. Reactivation requires a
separately accepted product decision. Historical bilingual implementation
remains a completed fact.

Every active report begins with a short plain-language Chinese overview for a
user with little option experience:

1. exact underlying and exact structure in beginner-readable language;
2. the final research disposition in plain Chinese, explicitly described as
   research priority rather than a buy/sell recommendation;
3. a small number of decisive supporting and caution reasons;
4. the key uncertainty, missing evidence, false-positive risk, or human-review
   question; and
5. concise future monetization, reassessment, and exit conditions.

The overview uses ordinary Chinese, briefly explains necessary option terms,
and avoids unexplained jargon, long methodology, complete metric/provenance
tables, uncalculated probabilities, and trade implications. Detailed
provenance, lineage, volatility and tail metrics, costs, liquidity, risk
calculations, expiration thresholds, scenarios, evidence, falsification,
methodology, limitations, and review questions remain below.

If `CandidateResearchRecord` and `ScreeningDecision` states differ, the
overview states that difference in one short plain-language sentence; details
retain both states and exact reason codes.

Permitted terminology includes “最终研究结论”, “是否值得进一步研究”,
“建议继续调查”, “建议观察”, “建议暂不继续”, and
“数据不足，无法负责地判断”. It must not say “建议买入”, “建议卖出”,
“强烈推荐交易”, “胜率”, “必然上涨”, or “必然下跌”. “最终建议” means
research disposition, not investment advice.

## 14. Explicit non-goals

The MVP does not:

- predict whether the underlying rises or falls;
- detect black swans with a probability score;
- recommend or execute trades;
- monitor positions or automate position management;
- promise positive returns;
- treat positive convexity, low IV, or flat skew as sufficient evidence;
- use narratives without numerical market confirmation;
- invent listed contracts or numerical evidence;
- rank candidates by investment attractiveness; or
- optimize a portfolio or position size.
