# Futu Provider Contract v0.1

## Status

This Tier-A contract freezes the smallest Futu OpenAPI boundary justified by
official documentation and sanitized live evidence from OpenD and futu-api
10.10.7008.

Futu is the preferred MVP U.S. market-data provider. Tiger remains an
unchanged, frozen fallback capability. This decision adds no provider router,
automatic fallback, arbitration, or data-source blending.

## Runtime and secret boundary

Futu OpenD owns user authentication and credentials. The provider module:

- connects only to an already-running OpenD instance;
- defaults to 127.0.0.1:11111;
- accepts explicit host and port arguments but reads no credentials;
- never reads, logs, returns, or stores account identifiers or passwords;
- imports the optional Futu SDK lazily; and
- sanitizes SDK construction and provider failures.

The repository does not consume the user external futu_api_config.properties
file and never treats its local path as a portable requirement.

## Public API

The direct module convexity_hunter.providers.futu exports exactly, in order:

    initialize_futu_quote_context
    FutuExactOptionContractVerification
    verify_futu_monthly_option_contract
    FutuBboEvidence
    FutuDirectEntryBboEvidence
    retrieve_futu_direct_entry_bbo_evidence
    retrieve_futu_underlying_daily_bars
    FutuHistoricalOptionBarEvidence
    retrieve_futu_historical_option_bar_evidence
    FutuExactOptionAnalyticsActivityEvidence
    retrieve_futu_exact_option_analytics_activity_evidence

Nothing is re-exported from convexity_hunter, convexity_hunter.providers, or
another package module.

## Exact caller-specified contract verification

verify_futu_monthly_option_contract accepts one caller-specified underlying,
expiration, call/put, and exact Decimal strike. It performs no nearest-strike
selection, ranking, broad scanning, or contract substitution.

The adapter requires:

- exactly one matching Futu expiration row classified MONTH;
- exactly one matching chain row with the exact underlying, expiration,
  call/put, and strike;
- an exact provider contract identifier consistent with those economics;
- option_standard_type equal to STANDARD;
- positive provider-supplied lot_size;
- exactly one matching snapshot row;
- option_valid equal to True;
- matching snapshot underlying, expiration, call/put, strike, and contract
  size; and
- a provider exercise type.

The resulting provider-neutral OptionContractReference retains the exact
provider symbol, multiplier, and exercise style. It remains
NormalizationQualityFlag.INCOMPLETE with deliverable_id=None and
settlement_type=None.

Futu exact STANDARD field is retained as authoritative provider-native
classification, but it does not disclose OCC deliverable contents or
corporate-action lineage and therefore does not by itself authorize the
existing complete StructureCosts path.

Reference endpoints supply no observation timestamp. Their adapter receipt
times are assigned explicitly and marked TIMESTAMP_ASSIGNED; receipt time is
not used for market observations.

## Current BBO evidence

retrieve_futu_direct_entry_bbo_evidence subscribes only to the exact verified
option and its exact underlying. It retains one qualifying atomic raw
Qot_UpdateOrderBook frame for each identifier.

A qualifying frame must contain, in the same protobuf frame:

- exact provider identity;
- non-crossed positive bid/ask values;
- positive bid/ask sizes;
- positive finite numeric svrRecvTimeBidTimestamp;
- positive finite numeric svrRecvTimeAskTimestamp; and
- timestamps no more than one second later than adapter receipt, solely to
  accommodate bounded independent-clock skew between OpenD and the local
  process; the raw provider timestamps are retained without rewriting.

An initial cached frame with absent or zero timestamps is ignored. Timeout,
subscription, schema, identity, crossed-market, timestamp, or disconnect
failure is sanitized and fails closed.

Because Futu's public context API has no handler getter and targeted
unsubscribe is not reliable enough to protect a shared context, the BBO
function consumes one dedicated QuoteContext. It validates the pinned futu-api
10.10.7008 boundary: no existing subscriptions and the default order-book
handler must still be installed. It then closes that context on every success
or failure path. A shared, subscribed, or custom-handler context fails before
mutation. Failure to validate, install, or close fails closed.

The one-second clock-skew tolerance does not establish freshness and does not
authorize canonical quote normalization. A larger server-clock lead fails
closed.

The result retains separate bid and ask server-receive timestamps and the
provider market state observed immediately before and after collection. It
does not claim those separate state reads were bound inside the BBO frame.

Official Futu documentation describes the numeric fields as Futu-server
receipt timestamps for bid and ask, while its interface limitations still
contain conflicting market-support wording. Futu also provides no single
event timestamp or authoritative quote-scope field in this frame. Therefore:

- no UnderlyingQuoteObservation is constructed;
- no OptionQuoteObservation is constructed;
- no QuoteScope value is assigned;
- no NBBO, consolidated, or provider-composite claim is made; and
- last-trade or snapshot update time never substitutes for BBO time.

This is immutable provider-native evidence only.

## Completed underlying daily bars

retrieve_futu_underlying_daily_bars calls request_history_kline with K_DAY and
AuType.NONE for one exact underlying and the caller range [begin_date,
end_date).

The adapter:

- translates Futu inclusive end date without widening the caller range;
- rejects ranges over 370 calendar days;
- requires the caller latest_completed_session_date;
- rejects incomplete, duplicate, unexpected, or out-of-range sessions;
- parses U.S. rows in America/New_York;
- retains raw unadjusted OHLC and volume;
- sets adjusted_close_price=None;
- sets adjustment_methodology=None; and
- creates existing UnderlyingDailyBarObservation records only for completed
  sessions.

No trading-calendar inference, interpolation, synthetic bar, fill, or
adjusted-close invention is permitted.

## Historical exact-option evidence

retrieve_futu_historical_option_bar_evidence calls request_history_kline with
K_DAY and AuType.NONE for the exact verified Futu option and [begin_date,
end_date).

Each immutable provider-native record retains exact contract verification,
Eastern session date, bar-start time, OHLC premiums, volume, turnover when
present, and retrieval time. It rejects incomplete sessions, duplicates,
malformed OHLC, negative counts, and identity or range mismatches.

Futu historical option rows do not supply exact historical open interest,
bid/ask, IV, or Greeks. No provider-neutral historical-option record exists,
so no such normalization is attempted. Failure to retrieve a previously known
expired contract remains an explicit provider limitation.

## Current analytics and activity

retrieve_futu_exact_option_analytics_activity_evidence retains the exact
snapshot volume, open interest, IV, Delta, Gamma, Theta, Vega, Rho, last-trade
timestamp when present, and retrieval time.

These fields remain provider-native because Futu does not bind:

- volume to a completed session;
- open interest to an effective date;
- IV or Greeks to an analytics observation time;
- analytics to a model, rate, or dividend methodology;
- Vega to an authoritative scaling convention; or
- Theta to an authoritative day basis.

No OptionVolumeObservation, OptionOpenInterestObservation,
OptionImpliedVolatilityObservation, or OptionGreeksObservation is built.

## Dependency and failure boundary

futu-api==10.10.7008 is an optional futu dependency. Normal tests use
synthetic SDK and context objects and require neither OpenD nor credentials.

All provider exceptions are replaced with stable sanitized messages. Error
messages, reprs, rows, payloads, account data, and credentials are never
embedded in exceptions or returned records.

## Explicit non-goals

This work adds no:

- trading, order, unlock, account, or portfolio API;
- broad option discovery or recommendation;
- provider router, fallback executor, arbitration, or blending;
- generic credential framework;
- current provider-neutral quote normalization;
- costs, liquidity, IV, Greeks, or OI normalization;
- expired-contract discovery;
- deterministic historical-IV reconstruction;
- structure generation, ranking, monitoring, alerts, or execution; or
- changes to Tiger implementation or its existing contracts.
