# AMZN volatility-environment feasibility v0.1

Date: 2026-09-16 (Asia/Shanghai)

Status: `FEASIBILITY_RECORDED / RV_OPERATIONALLY_BLOCKED`

Decision: `NO_PROVIDER_YET_PROVEN`

This is a bounded feasibility investigation, not a completed VolatilityEnvironment.
No production or business-contract change was made. One historical-daily runner
invocation timed out without a result; its adapter request stage is unknown.
No current option quote, account/config read, purchase, or retry was performed.
Fresh Git grounding found HEAD/main/origin/main equal to
`7495b5b2a0eae4497bda035568e6cb68fa36dd09` and a clean checkout before edits.
The prior 11:30 decision packages, 17 date checks and review were found in
external local notes, not Git. They had selected no policy and run no live probe.

Selected structure remains `US.AMZN261016C255000 + US.AMZN261016P255000`, the 2026-10-16 K255 Long Straddle. Authority remains `NEUTRAL_STRUCTURAL_RESEARCH`; `hypothesis_maturity_alignment=NOT_ESTABLISHED`. September 14 is the retained historical as-of, not today's date.

External note inputs, recorded by basename only: `vol-env-fallback-fit-2026-09-16.md`, `vol-env-rv-calendar-2026-09-16.md`, and `vol-env-futu-contract-fit-2026-09-16.md`.

## 3C.7d contract boundary

The executable contract is authoritative: [output type](../src/convexity_hunter/evidence.py), [transformer](../src/convexity_hunter/market_data_transformations.py), and [focused contract tests](../tests/test_market_data_transformations.py).

* Current selection: at least two expirations; tenor days must be unique; the
  reference tenor `T=32` must match exactly one current term point.
* Historical selection: exactly one expiry per expected session date, exact
  calendar tenor `expiration - session_date = 32`, strictly ascending dates,
  dates before current, and exact equality of the full IV-method tuple.
  `historical_sample_semantics=caller_declared_observation_sample`; calendar
  gaps are allowed because the dates are a declared observation sample, not an
  inferred complete exchange calendar.
* Each ATM candidate universe is caller-declared complete: no eligible paired
  call/put strike may be omitted. ATM uses the underlying BID/ASK midpoint;
  last price is not a fallback. Same-strike call/put IV is their arithmetic
  mean; no strike or expiry interpolation.
* 3C.7d has no Delta/Greeks requirement. Signed Delta, basis, premium
  adjustment, and the Tail model are future 3C.7e requirements. Do not impose
  a Tail `D×T` matrix on VolatilityEnvironment.

The later frozen clauses explicitly establish lineage `v0.2` in
[market-data-contracts.md](market-data-contracts.md), superseding the earlier §13.19
`v0.1` label. No unresolved contract conflict is recorded.

## RV prerequisite and checkpoint

Existing continuity input: `vol-env-rv-calendar-2026-09-16.md`. The frozen
caller policy is:

```text
policy: amzn-matched-rv-policy/v0.1
underlying/listing/currency: AMZN / XNAS / USD
current and RV end: 2026-09-14
RV start: 2026-08-13; calendar span: 32 days
price basis: RAW_CLOSE only
annualization: 252 sessions/year (explicit caller assumption)
returns/estimator: natural-log price ratio / sample variance
```

The RV preregistration uses this exact 22-session XNAS tuple [C1]; 2026-09-07 is
closed:

```text
2026-08-13, 2026-08-14,
2026-08-17, 2026-08-18, 2026-08-19, 2026-08-20, 2026-08-21,
2026-08-24, 2026-08-25, 2026-08-26, 2026-08-27, 2026-08-28,
2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04,
2026-09-08, 2026-09-09, 2026-09-10, 2026-09-11, 2026-09-14
```

This is request-shape evidence only. The bounded density
script is nominal arithmetic plus conditional overlays, not a general
authoritative calendar and not full 2023–26 calendar coverage; its omitted
2025-01-09 special closure does not affect the displayed Monday/Friday counts.

**RV execution: `TIMEOUT / TRANSPORT_OR_INITIALIZATION_UNKNOWN`.** One runner
invocation exceeded 180 seconds and was stopped with SIGINT; no remaining runner
process was found. Raw-daily request count/stage and graceful SDK close are unknown.
No bars, successful assessment, RV value or CalculationLineage was obtained.
No retry occurred; this does not establish provider data absence. The initial
external runner changed HOME and mislabeled record IDs as semantic keys; both
were corrected offline, without another acquisition. The run is operationally
inconclusive, not `MATCHED_RV_DEPENDENCY_READY`.

The policy is frozen before values: RAW_CLOSE is the existing adapter's only
evidenced basis; 252 is a transparent sessions/year assumption, not validated
annual trading frequency. Changing either requires a new policy version.
No adjusted-close model or total-return claim is introduced. Corporate-action
contamination has not been independently excluded. Historical freshness was
preregistered with a 45-day date-gap/retrieval-lag allowance, completed bars and
no partial/delayed/assigned evidence; it is not current-market freshness.

The two historical 3C.7d dates are preregistered as `D=2`:
`(2026-06-15, 2026-07-20)`, with nominal exact-`T=32` expiries
`(2026-07-17, 2026-08-21)`. No API-exposed historical option universe or live
probe establishes those cells yet. An exact-option historical IV row cannot
prove historical listing, pairing, or completeness.

### Nominal density only

For nominal third-Friday expiry `E`, set `S = E - 32` calendar days and count
`S` in `[2026-09-14 - N calendar months, 2026-09-14)`. The current pair
`S=2026-09-14, E=2026-10-16` is excluded. Session/holiday overlays are
diagnostic, not listing evidence.

| lookback N | nominal pairs | S is XNAS session | E not full-day holiday | both overlays |
|---:|---:|---:|---:|---:|
| 6 months | 6 | 6 | 5 | 5 |
| 12 months | 12 | 10 | 11 | 9 |
| 24 months | 24 | 20 | 22 | 18 |
| 36 months | 36 | 31 | 34 | 29 |

Six months is sparse: percentile granularity is `1/n` (20 percentage points
if only five observations survive); this is not an empirical validity threshold.
Lookback is not selected; regime/sample interpretation remains a decision.
Proposed eligibility grammar supports only a predeclared expiry class: this
example is `MONTH`, with nominal third-Friday `E` and `S=E-32` calendar days,
plus declared session overlays and independently returned exact historical
listing/quotes/IV/method. Do not automatically broaden it to weekly expiries
or cherry-pick cells based only on availability of quotes/native IV. Nominal
density is not actual AMZN option-listing proof. Exact-tenor eligibility is the
preferred policy family for contract fit, not a frozen complete sample policy.
Daily-60 admits structurally unmatched days; arbitrary weekly anchors can imply
nonstandard expiry weekdays. Six/twelve-month weekly sampling offers no automatic
fix. Longer lookbacks trade more observations for regime mixing; no governing
principle chooses 6/12/24/36 months, so lookback remains a human methodology decision.
Structural eligibility, provider availability and policy inclusion remain separate:
declare every eligible date from authoritative expiry/session evidence first;
report missing acquisition rather than deleting dates after observing IV.

## Current canonical gaps and Futu continuity

The existing `vol-env-futu-contract-fit-2026-09-16.md` is a static preflight
stop, not a live result. Current native option quote/IV/Greek fields are only
`PARTIAL`; historical option BBO and point-in-time option-universe capability
are `UNKNOWN`. Exact-option dated IV is at most `PARTIAL` because model
identity, method/version, unit normalization, and universe are absent.

The retained Futu contract reference is independently blocked by
`INCOMPLETE` metadata: deliverable and settlement are not established and the
3C.7d validator rejects incomplete/partial source evidence. This is not a
claim that every nullable field is absent; it is the specific canonical gap.
Current quote/session date, quote scope/phase/venue, complete pair identity,
and normalized direct-evidence metadata also remain unproven. No current or
historical Futu chain/quote integration proof is asserted.

| Futu area | Current/historical status | Required resolution |
|---|---|---|
| Historical underlying BBO | **UNKNOWN** — daily K-line/HV is not BBO; no historical as-of BBO surface. [F1][F3] | Provider semantics, or a new provider/contract. |
| Historical option quotes | **UNKNOWN** — historical bars lack bid/ask; current quote is not historical. [F1][F4] | Provider semantics, or a new provider/contract. |
| Historical IV | **PARTIAL** — exact-option dated native rows, but no common model/version/rate/dividend/unit identity. [F3] | Provider semantics; otherwise new provider/contract. |
| Historical universe / expiry | **UNKNOWN** — current chain/expiry methods do not expose point-in-time complete membership. [F2] | Provider semantics, or a new provider/contract. |
| Contract reference | **PARTIAL / INCOMPLETE** — deliverable/settlement are not established; validator rejects incomplete evidence. | Provider semantic completion, or new provider/contract. |
| Greeks / Delta | **N/A for 3C.7d** — future 3C.7e only; historical method remains unknown. | Tail semantics later; never a 3C.7d prerequisite. |

Futu fit: `PARTIAL`, not sufficient even with a satisfactory IV-model reply.
Live historical discoverability probe: `NOT_RUN / CONTRACT_DISCOVERY_UNAVAILABLE`
on the inspected public surface, not provider-global absence. The preregistration
uses the latest two nominal monthlies completed before the retained as-of;
sample dates are scheduled weekdays, but actual AMZN historical membership,
paired universe and expired lookup are unproved. Historical quote/BBO/Greeks
availability remains unknown; no failed lookup is labeled `NO_SUCH_EXPIRATION`.

## ORATS / Intrinio public field matrix

`DOCUMENTED` means the official page states the field/semantic. `PARTIAL`
means only part of the frozen requirement is stated. `UNKNOWN` means the
targeted official pass did not document the required semantic. `NOT_SUPPORTED`
requires an explicit contradiction; none is asserted from omission.
The IV-model hardgate in 3C.7d is common name/version/rate/dividend/unit metadata.
Broader spot/forward and Delta-convention diligence is not an extra 3C.7d gate.

| 3C.7d field or test | ORATS | Intrinio |
|---|---|---|
| Historical underlying BID/ASK midpoint vs close | **UNKNOWN** — public stock/spot and close fields do not document a historical underlying bid+ask pair or synchronized midpoint. [O1][O2][O3] | **UNKNOWN** — EOD close/OHLC and interval bid/ask fields do not document one synchronized historical EOD BBO midpoint. [I2][I3] |
| Option bid/ask primitive | **DOCUMENTED** — call/put bid/ask and NBBO fields. [O1][O2][O3] | **DOCUMENTED** — per-contract `close_bid`/`close_ask` and times. [I1][I4] |
| Paired quotes / complete candidate universe | **PARTIAL** — every-strike/every-expiry snapshot wording, but no caller-level no-omission/economic-identity proof. [O1][O2] | **PARTIAL** — dated exact chain rows, but no point-in-time no-omission/pair/deliverable proof. [I1][I5] |
| Exact expiry/date and repo tenor | **DOCUMENTED** — `tradeDate`/`expirDate`/`strike`; compute calendar tenor rather than trust `dte`. [O2][O3] | **DOCUMENTED** — exact expiration path, historical `date`, and output date/expiration. [I1][I5] |
| IV methodology / common unit | **PARTIAL** — mid IV, SMV, rate/residual fields and cleaning process; frozen common method/version/unit is incomplete. [O1][O3][O4] | **PARTIAL** — Black-Scholes IV and OTM mode; persisted method/version, rate/dividend descriptions, and exact unit semantics incomplete. [I1][I4] |
| Full model inputs / stable version | **UNKNOWN** — no frozen full input set, version, spot/forward, adjustment, or row-level provenance. [O1][O4] | **UNKNOWN** — recalc model choices/EOD underlying price are documented, but version, rates/dividends, basis, and provenance are not. [I1][I4] |
| Exact timestamp / EOD authority | **PARTIAL** — near-EOD is explicitly 14 minutes before close, not the closing print. [O1] | **PARTIAL** — date and per-field times exist, but close is last trade before close and synchronized EOD authority is not documented. [I1] |
| Corporate actions / direct vs reconstruction | **PARTIAL** — split/adjusted-price data and derived SMV/Greeks; option deliverable lineage and row-level provenance incomplete. [O2][O4] | **PARTIAL** — related symbols/factors and calculated/recalculable IV/Greeks; option deliverable lineage/provenance incomplete. [I1][I2][I4] |
| Signed Delta/model | **PARTIAL** — signed call/put convention documented, but this is future 3C.7e only. [O1] | **PARTIAL** — signed ranges/model choices documented, but future 3C.7e only. [I1][I5] |

Result: `NO_PROVIDER_YET_PROVEN`; neither ORATS nor Intrinio is justified as
PRIMARY or SECONDARY. Do not treat marketing or “complete chain” language as
integration proof.

## BBO decision options — no implementation

| option | consequence | disposition |
|---|---|---|
| Keep existing 3C.7d contract; add a new provider | Preserves the economic target: historical underlying BBO midpoint, paired ATM IV, exact dates/tenor. | Preferred only if authoritative inputs are proven; currently unproven. |
| Separate versioned close-ATM contract | Changes the economic target; does not repair remaining option-quote/reference gaps. | Requires a new contract/version; not implemented here. |
| Remain partial until authoritative inputs | Preserves the frozen contract and avoids close/BBO substitution. | Current decision. |

## Remaining closure conditions and validation

Before the first lawful artifact: complete the real matched-RV acquisition and
assessment; approve lookback/eligibility grammar and obtain every declared T32
historical paired universe; obtain canonical current (at least two expiries) and
historical underlying BBO, option quotes and complete references; obtain comparable
IV method/session/timing evidence and valid existing relationship proofs. Delta
and Tail matrices are not blockers for this sprint. A close-based ATM alternative
needs human methodology approval and a separate versioned contract; none is chosen.

Native IV/HV sidecar: prior two-call summaries demonstrate 20 common dates per
leg, zero null/nonfinite/duplicate/invalid-date counts and zero IV-HV arithmetic
mismatches. Actual values were not retained; ordering/jumps/divergence were not
reanalyzed or refetched. No percentile or screening gap was filled.

Validation: 17 focused RV/VolEnv tests and compileall passed; no full suite or
production change. Four-document link validation checked 76 local links; fences,
source-reference definitions and `git diff --check` passed. Final self-review
preserved the distinction between missing capability, unknown availability and
the inconclusive RV run. Operational evidence remains external and sanitized;
no raw payloads in Git.

## Evidence and official sources

No provider integration proof is asserted. Official source tags used above:

[O1]: https://orats.com/near-eod-data
[O2]: https://orats.com/docs/historical-data-api
[O3]: https://orats.com/docs/definitions
[O4]: https://orats.com/docs/core-research
[I1]: https://docs.intrinio.com/documentation/web_api/get_options_chain_eod_v2
[I2]: https://docs.intrinio.com/documentation/web_api/GetSecurityStockPrices_v2
[I3]: https://docs.intrinio.com/documentation/web_api/get_security_interval_prices_v2
[I4]: https://docs.intrinio.com/documentation/web_api/get_options_prices_eod_v2
[I5]: https://docs.intrinio.com/documentation/web_api/get_options_chain_v2
[F1]: https://openapi.futunn.com/futu-api-doc/en/quote/request-history-kline.html
[F2]: https://openapi.futunn.com/futu-api-doc/en/quote/get-option-chain.html
[F3]: https://openapi.futunn.com/futu-api-doc/en/quote/get-option-volatility.html
[F4]: https://openapi.futunn.com/futu-api-doc/en/quote/get-option-quote.html
[C1]: https://nasdaqtrader.com/Trader.aspx?id=Calendar
