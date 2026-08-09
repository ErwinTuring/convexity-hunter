# Tiger Exact Option-Contract Verification v0.1

## Status and purpose

This Tier-A contract freezes the second Tiger provider work unit. It accepts
one caller-specified option identity, retrieves Tiger's expiration evidence and
the exact expiration's option chain, and returns one verified provider-neutral
`OptionContractReference` together with the Tiger evidence needed to prove that
the expiration is provider-classified monthly.

Implementation status: complete and independently reviewed.

The work unit is verification, not discovery or recommendation:

```text
caller-specified UnderlyingKey + expiration + call/put + strike
    -> Tiger expiration evidence
    -> require exact provider period_tag == "m"
    -> Tiger chain for that exact expiration
    -> require exactly one exact matching row
    -> validate provider identifier and provider-supplied multiplier
    -> TigerExactOptionContractVerification
```

It does not scan for a desirable expiration, rank contracts, substitute a
nearby strike, choose Delta or ATM, apply the 30-150 DTE policy, or generate a
structure.

## Public boundary

The direct module `convexity_hunter.providers.tiger` adds exactly:

```text
TigerExactOptionContractVerification
verify_tiger_monthly_option_contract
```

Together with the completed local-runtime work unit, that direct module exports
exactly four names. No Tiger name is re-exported from `convexity_hunter` or
`convexity_hunter.providers`. The provider-neutral core does not import the
Tiger module or SDK.

The function signature is conceptually:

```python
verify_tiger_monthly_option_contract(
    quote_client,
    *,
    underlying_key,
    expiration,
    option_type,
    strike,
) -> TigerExactOptionContractVerification
```

`quote_client` is an already-initialized client. The function does not resolve
credentials, construct a client, grab quote permission, or call any trading
API. `underlying_key` must be an `UnderlyingKey`, `expiration` a date-only
value, `option_type` exactly `call` or `put` after existing core normalization,
and `strike` a positive `Decimal`.

The adapter records an aware UTC receipt timestamp immediately after each SDK
response returns and records normalization time after exact-row validation. A
caller cannot supply or override those timestamps because `retrieved_at` means
when the adapter actually received source material, not request-start time or a
caller-selected evaluation time.

## Authorized Tiger requests

The function performs exactly these market-data requests, in order:

1. `get_option_expirations(underlying_key.symbol, market="US")`;
2. only after monthly evidence succeeds,
   `get_option_chain(underlying_key.symbol, expiration.isoformat(),
   return_greek_value=False, market="US")`.

No permission-grab, quote-permission, quota, current-quote, historical-data,
dividend, rate, license, account, order, or execution request is authorized.
Raw SDK exceptions are replaced with stable sanitized runtime failures.

## Expiration evidence

The expiration response must expose the exact documented Tiger columns:
`symbol`, `date`, `timestamp`, and `period_tag`. Verification requires exactly
one row whose symbol equals the caller's canonical symbol and whose `date` is
the canonical ISO expiration date.

`period_tag` is provider evidence, not a locally inferred calendar rule. Its
value must be exactly `m`. Values including `w`, missing values, unknown values,
duplicate exact rows, and conflicting exact rows fail closed before the chain
request.

This establishes Tiger's monthly classification for this exact request. It
does not by itself freeze the product's future provider-neutral definition of
"standard monthly option" or establish DTE/event-window eligibility.

The exact provider expiration timestamp must be a non-Boolean integer and is
retained in the returned verification object. It is not used as a market-data
observation timestamp.

## Exact chain-row matching

The chain response must expose the exact documented Tiger columns:
`identifier`, `symbol`, `expiry`, `strike`, `put_call`, and `multiplier`.

Matching uses all caller-specified economic fields:

- chain `symbol` equals `underlying_key.symbol`;
- chain `expiry` equals the exact Tiger expiration timestamp retained from the
  expiration response;
- chain `strike`, converted with `Decimal(str(value))`, equals the caller's
  exact `Decimal` strike; and
- chain `put_call` is exactly `CALL` or `PUT` and equals the caller's type.

Exactly one row must match. Zero or multiple matches fail closed. The function
never chooses a nearest strike or another expiration.

The provider `identifier` must be a canonical OCC-style Tiger identifier with
a one-to-six-character padded root followed by `YYMMDD`, `C` or `P`, and an
eight-digit strike in thousandths. The decoded root, date, type, and strike
must agree with the matching row and caller request. Symbols whose provider
root cannot be proven identical are rejected rather than heuristically mapped.

`multiplier` must be a provider-returned non-Boolean integer greater than zero.
It is never defaulted to 100, inferred from the identifier, or supplied by the
caller.

## Returned evidence and normalization

`TigerExactOptionContractVerification` is frozen and contains exactly:

```text
provider_identifier
provider_period_tag
provider_expiration_timestamp_ms
contract_reference
```

Its invariants repeat the provider-identifier, monthly-tag, expiration,
option-type, strike, and multiplier consistency checks so direct construction
cannot represent contradictory evidence.

The nested provider-neutral record is an `OptionContractReference` whose:

- `OptionContractKey` uses the exact caller underlying, expiration, type, and
  strike plus the provider-supplied multiplier and underlying currency;
- `deliverable_id`, listing date, last-trade date, exercise style, and
  settlement type are `None` because this request does not establish them;
- two `SourceReference` values use provider-reference origin: dataset
  `option_expirations` retains the exact underlying/expiration evidence and
  dataset `option_chain` retains the provider identifier as both provider
  record ID and source symbol;
- each source's retrieved timestamp is captured immediately after its SDK
  response returns, and its observed timestamp equals that receipt timestamp
  under the declared assignment methodology because Tiger supplies no exact
  observation time for these reference terms;
- stable IDs are deterministically derived from the verified provider
  identifier and both canonical source-receipt timestamps;
- normalization methodology states that monthly classification and multiplier
  are provider supplied and that no contract-term timestamp was supplied; and
- normalization flags are `SYMBOL_MAPPED`, `TIMESTAMP_ASSIGNED`, and
  `INCOMPLETE`.

No quote, size, volume, open interest, IV, Greek, or raw chain payload is
retained in this result.

## Input and tabular boundaries

The function accepts the SDK's pandas DataFrame response and synthetic
DataFrame-equivalent test doubles exposing `to_dict("records")`. It copies only
the authorized scalar fields into local records. Missing columns, malformed
values, non-finite numeric values, Boolean numeric values, or unsupported table
objects fail with stable sanitized messages.

No raw response is logged, rendered, persisted, included in an exception, or
returned. Credentials, credential paths, Tiger/account identifiers, tokens,
secrets, licenses, request objects, and SDK client internals are never included
in the normalized record or verification object.

## Failure precedence

Observable validation and request precedence is:

```text
caller input types and canonical values
-> expiration request and table shape
-> exact expiration-row uniqueness
-> exact provider monthly tag
-> exact provider expiration timestamp
-> chain request and table shape
-> exact chain-row uniqueness
-> identifier proof
-> provider multiplier proof
-> normalized immutable result construction
```

Semantic failures use stable `TypeError` or `ValueError` messages. SDK/request
failures use stable `RuntimeError` messages. None echo SDK exception text or
provider payloads.

## Tests and live verification

Committed tests use fake clients and synthetic DataFrame-equivalent rows only.
They cover request order and exact arguments, fail-closed period tags, duplicate
and missing rows, strict identity matching, identifier contradictions,
multiplier validation, deterministic provenance, frozen output, sanitized SDK
failures, and public/import/network boundaries.

A post-test local smoke check may use the user's external provider-native
configuration to verify one caller-selected real contract. It must not print
credentials, account identifiers, raw payloads, or unredacted SDK errors and
must not write any live payload to the repository.

## Explicit exclusions

This work unit adds no option or underlying quote normalization, sizes, volume,
open interest, IV, Greeks, historical bars, dividends, rates, option-chain
discovery, DTE filtering, event-window policy, Delta or ATM resolution,
liquidity policy, structure generation, provider routing, fallback provider,
reporting, monitoring, scheduling, alerts, orders, or execution.
