# Futu SPY FOMC Browser-to-Direct-Entry Real Exercise

## Scope

On 2026-08-24, one repository-external sanitized exercise passed a current,
accepted Event Intelligence hypothesis through the existing Discovery Entry,
Futu Exact Contract Browser, explicit human selection, exact-verification
bridge, Direct Entry research service, deterministic screening, and Chinese
rendering. It added no product logic and made no trading call.

## Event Intelligence

The Federal Reserve's official calendar listed a two-day FOMC meeting on
2026-09-15 and 2026-09-16, associated with a Summary of Economic Projections:

<https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm>

State Street's official SPY product page identified SPY as the NYSE Arca-listed
SPDR S&P 500 ETF Trust and described its S&P 500 objective:

<https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy>

The source facts were kept separate from the interpretation that policy
communication and projections may widen SPY's return distribution. The mode
was `BIDIRECTIONAL_EXPANSION`; no direction was predicted. The inclusive
2026-09-16 through 2026-09-23 expected window was an explicit MVP exercise
assumption, not a Federal Reserve, State Street, market, or investment
forecast. Uncertainty included possible rescheduling, prior pricing, and a
muted, directional, or differently timed reaction. Acceptance returned
`ACCEPTED` with no issues.

With evaluation date 2026-08-24, the temporal gate passed and the deterministic
expiration interval was 2026-10-23 through 2027-01-21 inclusive.

## Browser and explicit selection

Live Futu chain evidence exposed three provider `MONTH` expirations:

```text
2026-11-20: 141 complete same-strike Call/Put pairs
2026-12-18: 158 complete same-strike Call/Put pairs
2027-01-15: 239 complete same-strike Call/Put pairs
```

The user explicitly chose 2026-11-20 as the nearest Browser-visible `MONTH`
expiration satisfying the existing maturity policy. That was a neutral MVP
experiment-design choice, not evidence of cheapness, liquidity, optimality, or
investment preference.

The Browser then displayed the middle 15 consecutive same-strike pairs in
neutral strike order. The user explicitly selected the median displayed strike
as one Long Straddle:

```text
Call: US.SPY261120C650000
Put:  US.SPY261120P650000
Expiration: 2026-11-20
Strike: 650
Quantity: 1 contract per leg
Assumed portfolio value: USD 10,000
Expected holding period: 30 calendar days
```

The holding period was an explicit MVP research assumption corresponding
approximately to 2026-08-24 through the declared expected-window end on
2026-09-23. Neither the expiry nor strike was labeled ATM, near-ATM,
Delta-selected, cheap, liquid, recommended, preferred, or a Discovery
candidate.

## Direct Entry result

Both selected Browser rows were retained by identity. Futu exact verification
ran once per leg, returned multiplier 100 for each leg, and preserved the exact
provider identifiers and economic fields. Both the bridge and service Direct
Entry exact-contract gates passed without substitution. Both provider-neutral
contract references remained `INCOMPLETE`, and research readiness remained
absent.

Partial Candidate Assembly received the caller-supplied `DATA_INSUFFICIENT`
research-record state. Deterministic screening independently returned
`DATA_INSUFFICIENT`; its six reason codes were:

```text
missing_costs
missing_liquidity
missing_volatility_environment
missing_structure_expiration_tail_slice
missing_target_move_scenario
missing_volatility_crush_scenario
```

The Chinese report contained 3,012 characters and SHA-256
`758003565b873c3d92349278a51181da1121331f5e25ae7a03902f35c9f6542c`.
No position-management plan was created because the prerequisite evidence was
not complete.

## Safety and meaning

The exercise persisted no raw provider payload and made no BBO, history,
account, or trading call. It did not infer deliverable status, quote freshness,
activity, open-interest semantics, IV or Greek methodology, costs, liquidity,
ATM, Delta, relative value, probability, or recommendation. It proves only the
current-event, explicit-human-selection minimum loop:

```text
accepted current event
-> SPY
-> bounded Futu Browser
-> explicit exact structure
-> exact identity verification
-> partial CandidateResearchRecord
-> DATA_INSUFFICIENT
-> Chinese report
```
