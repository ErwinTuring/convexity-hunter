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

Liquidity evidence must include:

- total-position quoted bid value
- total-position quoted ask value
- absolute bid-ask spread
- bid-ask spread relative to quoted midpoint
- minimum open interest across the structure’s legs
- minimum daily volume across the structure’s legs
- disclosed quote aggregation and timestamp methodology

These values expose the weakest-liquidity leg and the total-position execution market. The liquidity record stores evidence only; it does not define or apply sufficiency thresholds.

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

Each scenario result must record:

- base underlying price
- one base IV input for each declared option leg
- shocked underlying price
- one shocked IV for each declared option leg
- valuation date
- estimated total-position value
- entry cost basis
- estimated exit cost
- P&L after declared costs
- pricing methodology

The starting IVs must be the actual leg-level volatility inputs used by the pricing calculation; they are not automatically ATM IV. The default scenario applies the same relative IV shock to every leg’s own base IV, preserving existing differences across legs. This is a parallel proportional shock and does not model changes in skew, smile curvature, or term-structure shape. Richer volatility-surface shocks are deferred beyond MVP v0.1.

At expiration, leg-level IV inputs remain in the scenario result for auditability even when terminal payoff no longer depends on volatility. A scenario result stores a supplied pricing result and does not itself calculate option value, expected return, or probability-weighted forecasts. Its pricing methodology must describe the model or provider, rates, dividends, volatility-surface construction, interpolation, and limitations.

For MVP long-only structures, net liquidation value is floored at zero. When estimated exit cost exceeds estimated position value, the scenario assumes rational abandonment rather than paying to close. Scenario P&L therefore cannot be worse than negative entry cost. This bounded-loss treatment does not apply to future short-option structures, which are outside MVP v0.1.

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

### CandidateResearchRecord

`CandidateResearchRecord` is the canonical aggregate for one candidate structure. It stores a supplied CandidateState and rationale but does not derive the state. It enforces the same structure, underlying, as-of date, expiration, entry-cost basis, underlying-price basis, and quoted-midpoint consistency where relevant. It separates evidence by kind and impact and requires falsification conditions, false-positive reasons, and human-review questions.

WATCH, REJECT, and DATA_INSUFFICIENT records may remain incomplete, with missing data disclosed where required. INVESTIGATE records require minimum three-layer completeness. The aggregate does not define attractiveness thresholds or produce a recommendation.

INVESTIGATE also requires at least one supporting observed fact or supporting calculated metric. Assumptions and AI interpretations cannot independently satisfy this empirical-support requirement.

### User-facing reporting

User-facing reports must support separate Chinese and English output built from identical structured facts and numerical values. Every report must place a plain-language overview before the technical analysis. The overview must explain the structure, supplied state, supporting reasons, caution reasons, bounded loss, supplied scenario snapshot, and next human checks.

The overview must be derived deterministically from the research record and must not invent evidence, probabilities, prices, or conclusions. Complete auditable technical detail must remain below the overview. Localization is a presentation concern and must not change the candidate’s underlying economics.

## 9. Explicit non-goals

The MVP does not aim to:

- predict whether the underlying will rise or fall
- detect black swans with a probability score
- recommend trades
- execute orders
- promise positive returns
- treat low IV or flat skew as sufficient evidence
- use narratives without market confirmation
