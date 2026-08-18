# Real Direct Entry Vertical Slice Plan v0.1

## Purpose

This repository-grounded plan reorders near-term work around the shortest path
from one caller-specified real option to an auditable Chinese Convexity Hunter
research result. Market-data or pricing infrastructure is opened only when it
is a demonstrated blocker for this path.

This is a dependency and sequencing document, not an implementation contract.
Each Tier-A authority boundary still requires its own formal preflight and
frozen contract.

## Target slice

```text
one exact caller-specified Long Call or Long Put
    -> Futu exact monthly contract verification
    -> available authoritative evidence
    -> explicit None for unavailable reviewed artifacts
    -> reviewed candidate assembly
    -> ScreeningDecision
    -> Chinese report
```

The first slice is deliberately one leg. Long Straddle composition follows
only after the one-leg path proves its semantics and product value.

## A — Already producible and reusable

- Connection to an already-authenticated local Futu OpenD quote context.
- Exact caller-specified Futu monthly/provider-standard option verification
  with provider identifier, provider multiplier, and provider-neutral
  `OptionContractReference`.
- Tiger local-only configuration and completed evidence capabilities retained
  unchanged as fallback, without automatic routing or blending.
- Narrow SPY product-term enrichment using Tiger exact identity plus Cboe
  American/Physical terms. The reference remains `INCOMPLETE`: OCC's OSI
  convention does not make unsuffixed `SPY` plus multiplier 100 exact
  standard-deliverable proof, and known-adjusted and non-SPY contracts remain
  unsupported.
- Atomic Futu option/underlying BBO with exact identity and separate raw
  provider-server bid/ask receipt timestamps, retained provider-natively only.
- Futu provider-neutral underlying completed unadjusted daily bars.
- Futu provider-native exact-option historical OHLCV and current
  analytics/activity evidence; Tiger provider-native dividends remain
  available as fallback evidence.
- U.S. Treasury six-point daily par-yield curve and bounded pricing-rate proxy.
- Existing selected/fresh binding, timing, relationship, selection,
  liquidity, cost, realized-volatility, volatility-environment, tail-pricing,
  scenario-consumption, expiration-threshold, and affordability authorities
  when their required authentic inputs exist.
- Separate exact-contract and research-readiness verification, candidate
  assembly, screening, optional
  position-management, and Chinese-report services.
- Existing partial-candidate and `DATA_INSUFFICIENT` behavior.

Use these authorities; do not reproduce their formulas or policies in a new
service.

## B — Gaps to complete costs and liquidity

These gaps block complete research readiness. They do not block a
source-backed exact contract from entering partial candidate assembly and
producing `DATA_INSUFFICIENT`.

### B1. Current option quote semantics

Futu atomic Order Book Push proves exact contract identity, bid/ask values and
sizes, and separate provider-server bid/ask receipt timestamps. It does not
supply one authoritative event timestamp or bind market/session status inside
that same frame. Separate `get_market_state` reads do not repair this gap.
No `OptionQuoteObservation` or quote-scope claim is authorized.

### B2. Current underlying quote semantics

Futu atomic Order Book Push supplies exact underlying identity, BBO values and
sizes, and separate provider-server bid/ask receipt timestamps. As with the
option frame, it lacks one authoritative event timestamp and same-frame
market/session status. No `UnderlyingQuoteObservation` is authorized.

### B3. Exact-contract deliverable completeness

`StructureCosts` requires complete exact-contract reference evidence. OCC
explicitly permits rare unsuffixed non-standard options, including SPY FLEX
series consolidated to unsuffixed `SPY`; absence of an adjustment memo is not
proof. Cboe's public All Series data has no exact deliverable/adjusted/FLEX
field, while its Cash-Settled FLEX ETF file is underlying-level only. The
current product-term composite remains incomplete until a bounded authoritative
source proves the selected exact contract's deliverable. Do not build a generic
OCC platform solely to close this gap.

### B4. Activity and Greeks normalization

Liquidity requires provider-neutral current volume and open-interest records;
costs require provider-neutral Greeks with disclosed model, rate/dividend
inputs, unit convention, and Theta day basis. Current Futu and Tiger
provider-native analytics/activity evidence lacks sufficient
observation/session and methodology semantics. Volume lacks a session date and
completed-session status; open interest lacks its effective session date; and
IV/Greeks lack the required analytics time, model/input descriptions, Vega
scaling, and Theta day basis. Snapshot update time is a last-trade timestamp
and cannot timestamp the other fields. These records remain unavailable unless
new authoritative provider semantics emerge.

### B5. Thin current-snapshot composition

Only after B1–B4 are authoritatively available may one thin bridge build the
existing selected/fresh bindings and relationship selections for one exact
leg, then delegate to:

```text
transform_structure_liquidity
transform_structure_costs
verify_direct_entry_research_readiness
run_direct_entry_reviewed_research_service
```

It adds no numerical formula, screening rule, recommendation, or report logic.

## C — Acceptable as Data insufficient

For the first real slice, the following may remain absent and must be clearly
reported rather than fabricated:

- historical ATM IV and matched-horizon volatility environment;
- tail/skew term structure and historical skew percentile;
- non-expiration scenario values;
- expiration payoff thresholds when authentic costs are unavailable;
- affordability evidence when authentic costs or caller risk assumptions are
  unavailable; and
- forward-dividend completeness and historical IV/Greeks reconstruction.

The exact-contract verifier and service now expose the first minimal loop
without waiting for B1-B4:

```text
Futu exact OptionContractReference
    -> verify_direct_entry_exact_contracts
    -> run_direct_entry_reviewed_research_service with None artifacts
    -> DATA_INSUFFICIENT
    -> Chinese report
```

The existing assembler accepts optional reviewed artifacts for
`DATA_INSUFFICIENT`; the scanner deterministically identifies missing costs,
liquidity, volatility, tail slice, target scenarios, and crush scenario.
Missing-data descriptions remain explicit caller/product inputs and are never
silently generated by the generic assembler.

## D — Deferred sophistication

- curve bootstrapping, zero/OIS/SOFR platforms, extrapolation, and richer rate
  infrastructure;
- generic forward-dividend, historical-IV, Greeks-reconstruction, or
  volatility-surface platforms without a demonstrated blocker;
- Long Straddle orchestration before the one-leg slice;
- broad option-chain scanning, ranking, Delta/ATM generation, and structure
  generation;
- Event Intelligence and event-to-underlying mapping until real Direct Entry
  validates the Engine's practical use;
- provider routing/arbitration, general orchestration frameworks, monitoring,
  alerts, recommendation, sizing, portfolio optimization, and execution.

## Work-unit order and gate

```text
exact Futu monthly contract verification
    -> provider-neutral exact-contract verification
    -> first real Direct Entry DATA_INSUFFICIENT report
    -> retain proven provider-native Futu atomic BBO evidence
    -> resolve only the remaining same-frame quote/session semantic gap
    -> only proven normalized current-snapshot inputs
    -> liquidity and costs when every existing authority is satisfied
    -> evaluate product learning
    -> add only the next demonstrated blocker
```

Before opening any adjacent capability, apply this test:

> Does it materially shorten the path from one real exact option to an
> auditable Convexity Hunter research result?

If not, defer it.
