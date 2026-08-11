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
    -> Tiger exact monthly contract verification
    -> available authoritative evidence
    -> explicit None for unavailable reviewed artifacts
    -> reviewed candidate assembly
    -> ScreeningDecision
    -> Chinese report
```

The first slice is deliberately one leg. Long Straddle composition follows
only after the one-leg path proves its semantics and product value.

## A — Already producible and reusable

- Tiger local-only configuration discovery and `QuoteClient` initialization.
- Exact caller-specified monthly option verification with provider identifier,
  provider multiplier, and provider-neutral `OptionContractReference`.
- Narrow SPY product-term enrichment using Tiger exact identity plus Cboe
  American/Physical terms. The reference remains `INCOMPLETE`: OCC's OSI
  convention does not make unsuffixed `SPY` plus multiplier 100 exact
  standard-deliverable proof, and known-adjusted and non-SPY contracts remain
  unsupported.
- Transient entitled REST bid/ask/size evidence, retained only as
  provider-native evidence.
- Provider-neutral underlying completed daily bars.
- Provider-native historical dividend, historical option-bar, and exact-option
  analytics/activity evidence.
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

REST-chain quote evidence lacks authoritative quote timestamp and session
binding. The pending regular-session Option Push BBO probe must prove exact
contract identity, event time, bid time, ask time, bid/ask values and sizes,
and market/session status. Only proven Push evidence may enter a future
`OptionQuoteObservation`, initially with conservative
`QuoteScope.PROVIDER_COMPOSITE`.

### B2. Current underlying quote semantics

`StructureCosts` requires an exact current underlying bid/ask midpoint, but no
Tiger current-underlying `UnderlyingQuoteObservation` adapter exists. A
bounded feasibility review rejected REST `get_stock_briefs`: its
`latest_time` is a last-trade timestamp, not an event/bid/ask timestamp. The
same regular-session probe must instead test one atomic raw Push `QuoteData`
`ALL` frame for exact `SPY`, including event/bid/ask timestamps, Basic session
status/hour tag, and BBO values/sizes. Public Basic/BBO callback pairing is
insufficient. No normalized record is authorized before that evidence exists.

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
inputs, unit convention, and Theta day basis. Current Tiger provider-native
analytics/activity evidence lacks sufficient observation/session and
methodology semantics. The bounded applicability review is complete and
authorizes no normalization: volume lacks a session date and completed-session
status, open interest lacks its effective session date, and IV/Greeks lack the
required analytics time, model/input descriptions, Vega scaling, and Theta day
basis. `last_timestamp` is only the last-trade timestamp, and future Push BBO
quote evidence cannot fill these REST gaps. These records remain unavailable
unless new authoritative provider semantics emerge.

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
Tiger exact OptionContractReference
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
exact Tiger monthly contract verification
    -> provider-neutral exact-contract verification
    -> first real Direct Entry DATA_INSUFFICIENT report
    -> regular-session Option Push BBO evidence
    + current-underlying quote feasibility
    -> only proven normalized current-snapshot inputs
    -> liquidity and costs when every existing authority is satisfied
    -> evaluate product learning
    -> add only the next demonstrated blocker
```

Before opening any adjacent capability, apply this test:

> Does it materially shorten the path from one real exact option to an
> auditable Convexity Hunter research result?

If not, defer it.
