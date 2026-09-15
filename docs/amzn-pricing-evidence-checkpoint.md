# AMZN pricing-evidence checkpoint

## Scope and status

This is one sanitized, durable checkpoint for the 2026-09-14 AMZN Event Entry
continuation and the bounded offline historical-IV feasibility audit recorded on
2026-09-16 from prior data dated 2026-09-15. It is Tier C documentation-only work: no code, tests, contract,
provider adapter, methodology, or screening policy changed, and no evidence
BUILD is authorized. Await the bounded Futu support questionnaire before
integration or quote repeat. No private path, account, credential, pickle, raw
audit, or raw provider payload is copied here.

## AMZN Event Entry and partial Direct Entry checkpoint

The exact user-selected structure was:

```text
underlying: AMZN
structure: 2026-10-16 K255 Long Straddle
legs: US.AMZN261016C255000 + US.AMZN261016P255000
quantity: 1 per leg
assumed portfolio value: USD 10,000
expected holding: 14 calendar days
```

The 14-day holding period and USD 10,000 are user assumptions, not impact
duration, optimization, affordability proof, or recommendation. The accepted
hypothesis/request and neutral Browser context were retained, but original Event
Entry `UserEventInput`, preparation, selection, and translation objects were
not. The continuation used existing Direct Entry with sidecars; it was **not a
full ResearchCase replay** and did not rerun Event Intelligence.

One prior, now historical, quote batch had four chunks and 484 legs (242
straddles): 484/484 had asks and 472/484 were two-sided, with no retry/repeat.
Its authority remains `INDICATIVE_ONLY`; the underlying reference was a
completed 2026-09-11 close, not an authoritative current midpoint. It is not
current or formal liquidity evidence.

The path was `exact contract identity verification -> existing partial Direct
Entry -> candidate/screening DATA_INSUFFICIENT`.

The six unchanged screening reasons are `missing_costs`, `missing_liquidity`,
`missing_volatility_environment`, `missing_structure_expiration_tail_slice`,
`missing_target_move_scenario`, and `missing_volatility_crush_scenario`.

Research readiness and PMP are absent; no management conditions were supplied.
Exact deliverable/settlement remains `INCOMPLETE`; maturity is
`NEUTRAL_STRUCTURAL_RESEARCH / NOT_ESTABLISHED`.

Separate operational metadata: the prior initialization failure was a script
`status.name` bug with zero provider calls, not a provider failure. The one-shot
automation is `DELETED`, not paused; neither fact is market evidence.

## Native historical-IV rerun

The native summary records two of two exact-option calls returned for the AMZN
Call/Put pair, with `query_time_period = Month` and `hv_time_period = 30`.
Each returned 20 dated rows over 2026-08-17 through 2026-09-14; the common set
is:

```text
2026-08-17  2026-08-18  2026-08-19  2026-08-20  2026-08-21
2026-08-24  2026-08-25  2026-08-26  2026-08-27  2026-08-28
2026-08-31  2026-09-01  2026-09-02  2026-09-03  2026-09-04
2026-09-08  2026-09-09  2026-09-10  2026-09-11  2026-09-14
```

Both rowsets had zero null, duplicate, invalid-date, and nonfinite counts, and
the IV/HV/premium consistency check had zero mismatches. This is partial
**provider-native capability only**: no actual IV series was persisted, no
normalized inputs or provider-neutral `OptionImpliedVolatilityObservation`
were created. Historical Delta/Greeks, exact-tenor and complete-universe
semantics, supplier model/version, rate/dividend inputs, and authoritative
EOD/valuation selection remain `NOT_ESTABLISHED` for this evidence.

## Bounded offline exact-DTE feasibility audit

The retained current expiration set is exactly:

```text
E_retained = {2026-10-16, 2026-11-20, 2026-12-18, 2027-01-15}
```

Conditionally using 2026-09-14 as the current as-of date, pure Gregorian
arithmetic gives the four current tenors:

| expiration | calendar DTE |
| --- | ---: |
| 2026-10-16 | 32 |
| 2026-11-20 | 67 |
| 2026-12-18 | 95 |
| 2027-01-15 | 123 |

The 20 returned dates are an availability observation, not a selected sample.
Conditionally, 2026-09-14 is current and is excluded from historical dates:

| arithmetic item | count |
| --- | ---: |
| returned native dates | 20 |
| preceding date labels (not validated sessions/samples) | 19 |
| current tenors (`T`) | 4 |
| required `D × T` cells if those 19 dates were declared `D` (`19 × 4`) | 76 |
| retained current expiration dates | 4 |

After excluding the current 2026-09-14 label, the 19 preceding labels would
require 76 `D × T` cells if the caller declared those labels as `D` historical
dates; this is not an admissibility result. For 2026-09-11, the four exact-tenor
historical expiries would be 2026-10-13, 2026-11-17, 2026-12-15, and 2027-01-12
(zero in `E_retained`). The retained current set is not a historical universe
and is not substituted for any historical cell.

This proves only calendar arithmetic and matrix size. It does not claim any
required expiry was absent, invalid, unlisted, unavailable, or a holiday, and
makes no exchange-calendar, session, close-time, or listing inference. Lookup,
lookback, and `D` sampling policies are unset as caller/research-policy inputs,
not Futu decisions; no dates were selected or cherry-picked, and no strike,
tenor, Delta, or surface interpolation occurred.

## Contract boundary and outcome

The volatility source checks exact current-tenor uniqueness, reference-tenor
matching, historical date/tenor identity, common IV methodology, and realized-
window endpoint/span correspondence
(`src/convexity_hunter/market_data_transformations.py:4925-5018`). The tail
source retains current expiration/tenor parameters and historical counts after
its selection path (`src/convexity_hunter/market_data_transformations.py:6860-6904`).

The frozen 3C.7e contract requires exactly `D × T` selections keyed by
`(session_date, expiration - session_date)`; gaps are permitted, current is
excluded, EOD is caller-declared, and no exchange calendar or missing date is
inferred (`docs/market-data-contracts.md:5868-5884`). It requires
nearest-observed signed Delta with no interpolation
(`docs/market-data-contracts.md:5802-5827`).

Outcome: **no READY evidence BUILD**. Supplier methodology, historical
expiry/universe authority, and historical Delta/Greeks authority remain
`NOT_ESTABLISHED` pending Futu support. Caller lookup/lookback/`D` sampling is a
separate undeclared research-policy input, not a provider decision. Native IV/HV
can only be a separately reviewed descriptive context path; it cannot fill
paired exact-tenor ATM or Tail inputs. Six screening gaps and all authority
states remain unchanged.

## Read-only evidence register

Named evidence, by basename/output label only: `futu-pricing-input-verification-2026-09-15.md`,
`AMZN-explicit-inputs.json`, `AMZN-reviewed-result-summary.json`,
`AMZN-reviewed-research-zh-CN.md`, `AMZN-event-entry-sanitized-summary.json`,
and `futu-historical-iv-rerun/summary.json`.

This documentation-only checkpoint added no new provider acquisition or production tests.
