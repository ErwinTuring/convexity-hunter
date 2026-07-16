# MVP Specification

Convexity Hunter v0.1 identifies option structures that deserve further investigation as potential cheap positive-convexity opportunities. It does not predict market direction or issue trade recommendations.

## 1. MVP research question

The system must answer:

> Which concrete option structures currently deserve further investigation because their downside is bounded and bearable, their payoff is positively convex, and the market may be underpricing that convexity?

The output is not merely a list of assets. Each final candidate must identify a concrete option structure with enough detail to evaluate its payoff, costs, and total-position risk.

## 2. Scope

MVP v0.1 is limited to:

- US-listed equities and ETFs
- long options only
- long calls, long puts, and long straddles
- one strategy position at a time, containing one or two long-option legs
- no option selling
- no spreads
- no automatic execution
- no portfolio optimization
- no precise probability forecasts
- no LLM-generated numerical market data

A long call or long put contains one leg. A long straddle contains one long call and one long put with the same underlying, strike, and expiration. No other multi-leg structures are included in MVP v0.1.

Limiting the MVP to long-option structures makes maximum loss explicitly bounded by the premium and associated costs. The system must still determine whether that loss is bearable relative to the assumed portfolio value and repeated-bet costs.

## 3. Three-layer screening model

### Layer 1: Volatility pricing environment

**Purpose:** Determine whether the overall option-pricing environment is relatively quiet or expensive.

**Required evidence:**

- ATM implied volatility
- ATM IV percentile
- ATM IV relative to its historical median
- implied-volatility term structure
- matched-horizon implied-versus-realized volatility gap

**Matched-horizon comparison:** A 30-day IV must be compared with realized volatility over a comparable horizon using a consistent annualization method.

Low IV percentile is only an investigation signal. It is not proof that options are cheap.

IV percentile and historical median ATM IV must disclose the number of historical observations used to calculate them.

### Layer 2: Tail relative pricing

**Purpose:** Determine whether either tail is relatively cheap or expensive compared with ATM options and with its own history.

**Required evidence:**

- 25-delta put IV minus ATM IV
- 25-delta call IV minus ATM IV
- 10-delta versus 25-delta wing curvature
- current skew percentile relative to the asset’s own history
- skew term structure across expirations

Steep put skew often means downside protection is relatively expensive. Flat skew may indicate cheaper downside protection, but it is not proof of mispricing. Skew is a relative-price measure, not a complete measure of absolute cheapness.

Skew percentile must disclose its number of historical observations. The 10-delta and 25-delta measurements must disclose their delta convention and interpolation methodology.

For MVP v0.1, one historical observation means one valid US market trading session using one end-of-day observation per session. Intraday, weekly, calendar-day, and mixed-frequency percentile histories are outside scope.

### Layer 3: Concrete structure validation

**Purpose:** Determine whether a specific long-option structure provides attractive and bearable convexity after costs.

Each candidate must include:

- underlying symbol
- option type or structure
- direction
- strike or strikes
- expiration
- contract multiplier
- assumed position size
- quoted midpoint premium
- estimated spread cost
- commissions and fees
- total estimated entry cost
- maximum loss
- maximum loss as a percentage of assumed portfolio value
- bid-ask spread
- theta
- raw total-position gamma
- local Gamma P&L approximation for a 1% underlying move
- local Gamma-cost ratio for a 1% underlying move
- break-even point or points
- scenario P&L for defined underlying moves
- scenario P&L for defined volatility changes
- expected holding horizon
- cumulative cost if the same type of bet fails repeatedly

The local Gamma approximation is a second-order local measure, not complete scenario P&L. It excludes Delta, Vega, Theta, volatility-surface changes, jumps, and model error, and it must not be presented as expected profit.

For MVP v0.1, all monetary values in structure costs are total-position USD values. Quoted midpoint premium is the total option premium for the complete strategy position at quote midpoint and excludes spread cost, commissions, and fees. Estimated spread cost is the estimated execution cost above quote midpoint for the total strategy position. No currency field is required while scope remains limited to US-listed equities and ETFs.

Gamma is the total strategy-position second derivative `d²V/dS²`, expressed as USD of position-value change per USD² of underlying-price movement. It must already incorporate every leg, quantity, and contract multiplier. Data adapters must convert provider-specific per-share or per-contract Gamma before constructing structure costs. The local Gamma formulas are valid only under this unit convention.

Theta per day is the total strategy-position Theta expressed as USD of position-value change for one day under the declared methodology. The methodology must disclose the source or pricing model, Gamma scaling, Theta day-count convention, and relevant interpolation or calculation assumptions. The numeric field does not impose a 252-day or 365-day convention.

The final candidate is a structure, not an asset.

## 4. Scenario framework

The system must analyze scenarios rather than predict direction.

Every scenario P&L result must identify its valuation time. Initial valuation-time scenarios are:

- immediate shock, with no passage of time
- 7 calendar days later
- at the declared expected holding horizon
- at expiration

A candidate report may use a relevant subset, but it must never present scenario P&L without stating the valuation time. Scenario valuation must account for remaining time to expiration.

**Minimum price scenarios:**

- underlying move of -20%
- -10%
- -5%
- 0%
- +5%
- +10%
- +20%

**Minimum volatility scenarios:**

- IV change of -20%
- unchanged
- +20%
- +50%

The MVP default IV shocks are relative changes from current IV:

`shocked IV = current IV × (1 + IV shock)`

For example, a +20% IV shock changes an IV of 20% to 24%, not 40%. Absolute percentage-point shocks may be added later, but they must be explicitly labeled.

Scenario ranges may later be adapted to each asset. These values are the initial MVP defaults.

## 5. Candidate states

The MVP must not create an unsupported numerical Convexity Score. It uses four states:

- **Reject:** The structure fails bounded-loss, affordability, liquidity, convexity, or cost tests.
- **Watch:** Some evidence is interesting, but the structure is not currently attractive or the evidence is incomplete.
- **Investigate:** The structure passes the initial three-layer screen and deserves deeper human research.
- **Data insufficient:** Required market or historical data is unavailable or unreliable, so the screen cannot be completed responsibly.

## 6. Evidence classification

Every output must clearly separate:

- **Observed fact:** Market or reference data obtained from an identified source.
- **Calculated metric:** A reproducible value derived from observed data.
- **Assumption:** A declared input used where a value or future condition is not observed.
- **AI interpretation:** An explanation, critique, or hypothesis derived from the evidence.

The LLM may explain and critique evidence, but it must not invent prices, implied volatility, Greeks, probabilities, or historical values.

## 7. Falsification requirements

Every investigation candidate must include:

- what evidence supports the hypothesis
- what evidence weakens it
- what market change would invalidate the opportunity
- what data is missing
- why the candidate might be a false positive

## 8. MVP output

One candidate report must contain:

- investigation state
- concrete option structure
- bounded-downside summary
- volatility-environment evidence
- tail-pricing evidence
- costs and liquidity
- scenario payoff table
- supporting evidence
- contradictory evidence
- falsification conditions
- missing data
- AI interpretation
- human-review questions

## 9. Explicit non-goals

The MVP does not aim to:

- predict whether the underlying will rise or fall
- detect black swans with a probability score
- recommend trades
- execute orders
- promise positive returns
- treat low IV or flat skew as sufficient evidence
- use narratives without market confirmation
