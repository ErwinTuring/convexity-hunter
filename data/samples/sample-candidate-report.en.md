# Convexity Hunter Research Record

> **SYNTHETIC DEMONSTRATION — NOT CURRENT MARKET DATA AND NOT A TRADE RECOMMENDATION**

## Plain-language overview

### 1. What is being studied?

This report studies buying a call and a put with the same strike and expiration. It does not require choosing an up or down direction in advance, but the underlying must move enough during the holding period to overcome premium, time decay, and trading costs.

- **Underlying:** SPY
- **Structure type:** long_straddle
- **Strike or strikes:** $500.00
- **Expiration:** 2030-02-16
- **Expected holding days:** 14

### 2. What is the current status?

- **State:** watch
- **State rationale:** WATCH is supplied only to exercise the report model and is not a screening conclusion.

This status is supplied by the research record. Milestone 1.1 does not independently calculate it, and it is not a trade recommendation.

### 3. Why might it deserve attention?

- Synthetic reference ATM IV is at the 28th historical percentile and 2.50 percentage points below its historical median. This is only an investigation signal and is not proof that options are cheap.

### 4. Why is caution still necessary?

**Weakening evidence**

- Synthetic reference ATM IV exceeds matched-horizon realized volatility by 2.50 percentage points.
- Synthetic repeated entry costs would consume 7.45% of the assumed portfolio across three attempts.

**Missing data**

- No current or historical market data has been supplied.
- No independently validated pricing output has been supplied.

### 5. How much could be lost?

For supported long-only MVP structures, the declared maximum modeled loss is the total entry cost.

- **Total entry cost:** $2,482.60
- **Maximum loss:** $2,482.60
- **Maximum loss percentage:** 2.48%
- **Repeated-bet count:** 3
- **Cumulative repeated-bet cost:** $7,447.80
- **Cumulative repeated-bet percentage:** 7.45%

### 6. What happens in the supplied scenarios?

Among the supplied scenarios: 3 positive, 1 negative, and 0 zero P&L results.

Highest result among supplied scenarios: expiration; underlying move -20.00%; IV shock 0.00%; P&L after costs $7,517.40.

Lowest result among supplied scenarios: immediate; underlying move 0.00%; IV shock -20.00%; P&L after costs -$912.60.

This compares only the scenarios supplied in the report. It does not represent every possible outcome and is not a return forecast.

### 7. What should a human verify next?

**Human-review questions**

1. Are the synthetic cost fields internally understandable?
2. Does each scenario disclose enough methodology for audit?
3. Which real-data controls are required before this format is used for research?

**Conditions that would overturn the research hypothesis**

1. Volatility-environment support fails if real data show that structure-relevant ATM IV is not below its own historical median under the declared methodology.
2. The convexity-versus-cost hypothesis fails if reproducible valuation using real quotes shows that reasonable two-sided move scenarios do not overcome entry cost, time decay, and estimated exit cost over the expected holding horizon.

---

## Technical research details

- **Candidate ID:** SYNTHETIC-SPY-STRADDLE-001
- **State:** watch
- **State rationale:** WATCH is supplied only to exercise the report model and is not a screening conclusion.
- **As-of date:** 2030-01-02
- **Underlying:** SPY
- **Structure type:** long_straddle
- **Expiration:** 2030-02-16
- **Expected holding days:** 14

### Research hypothesis

A synthetic SPY long straddle may merit further investigation if its declared convex payoff paths appear favorable relative to total-position costs.

### Concrete option structure

| Leg | Type | Strike | Expiration | Quantity | Multiplier |
| ---: | --- | ---: | --- | ---: | ---: |
| 1 | call | $500.00 | 2030-02-16 | 1 | 100 |
| 2 | put | $500.00 | 2030-02-16 | 1 | 100 |

### Bounded downside and costs

- **Assumed portfolio value:** $100,000.00
- **Quoted midpoint premium:** $2,400.00
- **Estimated spread cost:** $80.00
- **Commissions and fees:** $2.60
- **Total entry cost:** $2,482.60
- **Maximum loss:** $2,482.60
- **Maximum loss percentage:** 2.48%
- **Repeated-bet count:** 3
- **Cumulative repeated-bet cost:** $7,447.80
- **Cumulative repeated-bet percentage:** 7.45%
- **Theta per day:** -$45.00
- **Total-position Gamma:** 0.55
- **Local Gamma P&L for a 1% move:** $6.88
- **Local Gamma-cost ratio for a 1% move:** 0.29%
- **Greeks methodology:** synthetic fixture Greeks; total-position scaling by quantity and multiplier; synthetic daily theta convention

### Liquidity

- **Total-position bid:** $2,320.00
- **Total-position ask:** $2,480.00
- **Quoted midpoint:** $2,400.00
- **Absolute bid-ask spread:** $160.00
- **Bid-ask spread percentage:** 6.67%
- **Minimum leg open interest:** 1200
- **Minimum leg daily volume:** 350
- **Quote methodology:** synthetic fixture total-position quote assembled from synthetic leg quotes

### Layer 1 — Volatility pricing environment

- **Reference tenor:** 30 days
- **ATM IV:** 20.00%
- **IV percentile:** 28.00%
- **IV history observations:** 252
- **Historical median ATM IV:** 22.50%
- **ATM IV minus historical median:** -2.50%
- **Matched realized volatility:** 17.50%
- **Matched realized window:** 30 days
- **Implied-realized gap:** 2.50%

| Tenor days | ATM IV |
| ---: | ---: |
| 30 | 20.00% |
| 60 | 21.50% |

### Layer 2 — Tail relative pricing

| Expiration | Days to expiration | ATM IV | 25Δ put IV | 25Δ call IV | Downside 25Δ skew | Upside 25Δ skew | Downside wing curvature | Upside wing curvature | Skew percentile | History observations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2030-02-16 | 45 | 20.00% | 21.80% | 20.50% | 1.80% | 0.50% | 2.70% | 1.40% | 32.00% | 252 |
| 2030-03-15 | 72 | 21.00% | 23.10% | 21.40% | 2.10% | 0.40% | 3.10% | 1.50% | 38.00% | 252 |

- **2030-02-16 delta methodology:** synthetic fixture spot-delta convention with synthetic linear IV interpolation
- **2030-03-15 delta methodology:** synthetic fixture spot-delta convention with synthetic linear IV interpolation

### Scenario analysis

| Valuation time | Valuation date | Underlying move | IV shock | Shocked underlying | Base IVs | Shocked IVs | Position value | Exit cost | Net liquidation value | P&L after costs | Return on entry cost |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| immediate | 2030-01-02 | -10.00% | 50.00% | $450.00 | Call: 19.80%; Put: 20.20% | Call: 29.70%; Put: 30.30% | $5,200.00 | $90.00 | $5,110.00 | $2,627.40 | 105.83% |
| immediate | 2030-01-02 | 0.00% | -20.00% | $500.00 | Call: 19.80%; Put: 20.20% | Call: 15.84%; Put: 16.16% | $1,600.00 | $30.00 | $1,570.00 | -$912.60 | -36.76% |
| holding_horizon | 2030-01-16 | 15.00% | 20.00% | $575.00 | Call: 19.80%; Put: 20.20% | Call: 23.76%; Put: 24.24% | $9,000.00 | $110.00 | $8,890.00 | $6,407.40 | 258.09% |
| expiration | 2030-02-16 | -20.00% | 0.00% | $400.00 | Call: 19.80%; Put: 20.20% | Call: 19.80%; Put: 20.20% | $10,000.00 | $0.00 | $10,000.00 | $7,517.40 | 302.80% |

- **Pricing methodology:** synthetic fixture supplied valuations; illustrative model assumptions for rates, dividends, proportional IV shocks, and interpolation; no pricing performed

Scenario values are supplied research results, not expected returns or probability-weighted forecasts.

### Evidence

#### Supporting evidence

- **Evidence ID:** SYNTHETIC-CALC-SUPPORT
  - **Kind:** calculated_metric
  - **Statement:** Synthetic reference ATM IV is at the 28th historical percentile and 2.50 percentage points below its historical median. This is only an investigation signal and is not proof that options are cheap.
  - **Source:** synthetic fixture volatility-environment data
  - **Methodology:** synthetic fixture percentile and median comparison using 252 end-of-day observations

#### Weakening evidence

- **Evidence ID:** SYNTHETIC-CALC-WEAKEN-IV-GAP
  - **Kind:** calculated_metric
  - **Statement:** Synthetic reference ATM IV exceeds matched-horizon realized volatility by 2.50 percentage points.
  - **Source:** synthetic fixture volatility-environment data
  - **Methodology:** synthetic fixture matched 30-day annualized implied-versus-realized comparison
- **Evidence ID:** SYNTHETIC-CALC-WEAKEN
  - **Kind:** calculated_metric
  - **Statement:** Synthetic repeated entry costs would consume 7.45% of the assumed portfolio across three attempts.
  - **Source:** synthetic fixture structure-cost inputs
  - **Methodology:** synthetic fixture total entry cost multiplied by three attempts

#### Neutral evidence

- **Evidence ID:** SYNTHETIC-ASSUMPTION
  - **Kind:** assumption
  - **Statement:** The expected holding period is assumed to be 14 calendar days.
  - **Source:** synthetic fixture research assumption
  - **Methodology:** synthetic fixture declared holding-horizon assumption
- **Evidence ID:** SYNTHETIC-AI-INTERPRETATION
  - **Kind:** ai_interpretation
  - **Statement:** The synthetic evidence is mixed and warrants human review rather than a conclusion.
  - **Source:** synthetic fixture interpretation
  - **Methodology:** synthetic fixture deterministic narrative supplied by the example

### Falsification conditions

1. Volatility-environment support fails if real data show that structure-relevant ATM IV is not below its own historical median under the declared methodology.
2. The convexity-versus-cost hypothesis fails if reproducible valuation using real quotes shows that reasonable two-sided move scenarios do not overcome entry cost, time decay, and estimated exit cost over the expected holding horizon.

### Missing data

- No current or historical market data has been supplied.
- No independently validated pricing output has been supplied.

### False-positive risks

- Invented values may accidentally resemble a favorable historical configuration.
- The simplified proportional IV shocks do not model skew or surface changes.

### AI interpretation

Interpretation only: this synthetic fixture demonstrates report organization and does not establish that any real option structure is attractive.

### Human-review questions

1. Are the synthetic cost fields internally understandable?
2. Does each scenario disclose enough methodology for audit?
3. Which real-data controls are required before this format is used for research?

This record organizes research evidence. It does not recommend, execute, or guarantee any trade or investment outcome.
