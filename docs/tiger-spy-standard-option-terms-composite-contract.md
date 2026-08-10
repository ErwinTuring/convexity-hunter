# Tiger + OCC/Cboe SPY Standard Option Terms Composite v0.1

## Status and purpose

Formal Tier-A preflight is complete and this contract freezes one narrow
reference-data composition required by the first real SPY Direct Entry slice.

Tiger's exact monthly-contract verification authoritatively supplies the
listed contract identity, monthly classification, strike, option type, and
provider multiplier, but intentionally leaves exercise style and settlement
type unknown. The existing cost transformation rejects such an incomplete
reference and requires exact `American` / `Physical` terms.

Cboe's public S&P option-product comparison identifies standard SPDR ETF
(`SPY`) options as American-style contracts settled by delivery of underlying
shares. OCC Information Memo 26853 establishes the OSI symbol boundary: an
adjusted non-standard contract uses a numeric root suffix, while an unchanged
root denotes the standard contract; adjustments that retain the unchanged root
also retain standard contract terms. This unit combines only those invariant
SPY product and OSI terms with one already verified exact Tiger monthly
contract. It does not weaken any core validation or alter the original Tiger
verification.

## Public boundary

The direct module `convexity_hunter.providers.tiger` appends exactly:

```text
compose_tiger_spy_standard_option_contract_reference
```

The function signature is:

```python
compose_tiger_spy_standard_option_contract_reference(
    verification,
    *,
    normalized_at,
) -> OptionContractReference
```

Nothing is re-exported from a package root. The function performs no network,
SDK, credential, filesystem, environment, clock, quote, or trading operation.

## Exact accepted input

`verification` must have exact type
`TigerExactOptionContractVerification` and retain all existing intrinsic
invariants. Its provider period tag must be exactly `m`. Its unchanged Tiger
reference must have:

```text
underlying symbol = SPY
listing MIC = ARCX
security type = ETF
currency = USD
contract multiplier = 100, supplied by Tiger
deliverable_id = None (not yet established by the Tiger source alone)
exercise_style = None
settlement_type = None
record origin = provider_reference
normalization version = tiger-option-contract-v0.1
quality flags = symbol_mapped, timestamp_assigned, incomplete
exactly the verified option_expirations and option_chain Tiger sources
```

The multiplier is validated, preserved, and never defaulted. The provider
identifier must decode to the exact unsuffixed OSI root `SPY`; padded spaces in
the six-character root field are permitted, but any digit, alternate root, or
other non-space suffix fails closed. This explicit root proof, not the input's
`deliverable_id=None` by itself, establishes the standard-deliverable boundary.
Any nonstandard, adjusted, alternate-root, nonmonthly, non-SPY, or already
completed/conflicting reference fails closed.

`normalized_at` must be an aware datetime, normalize to UTC, and not precede
the Tiger sources, original Tiger normalization, or either frozen authority
capture.

## Frozen authority declarations

The first additional immutable source declaration is:

```text
provider = Cboe Global Markets
dataset = S&P Index Options Product Suite Comparison
provider record = SPDR ETF (SPY)
URI = https://www.cboe.com/tradable-products/product-comparison/
verified date = 2026-08-10
assigned source time = 2026-08-10T00:00:00Z
```

It establishes exact SPY product-level exercise and settlement terms.

The second additional immutable source declaration is:

```text
provider = The Options Clearing Corporation
dataset = OCC Information Memos
provider record = 26853
URI = https://infomemo.theocc.com/infomemos?number=26853
verified date = 2026-08-10
assigned source time = 2026-08-10T00:00:00Z
```

It establishes the OSI adjusted-root boundary. The exact Tiger identifier is
decoded using the already frozen Tiger verifier; an unsuffixed `SPY` root is
therefore standard, while a numeric suffix is adjusted/non-standard. The
provider-supplied multiplier must independently equal 100. Neither authority
overrides a contradictory Tiger identity.

The Cboe page has no machine-readable publication or effective timestamp for
these terms. The OCC memo has a publication date but no timestamp. Each nominal
UTC-midnight timestamp records the manual verification date and is explicitly
assigned; neither is represented as an exchange event time, contract listing
time, or current market observation. The source declarations are versioned
code reference data. Runtime retrieval is not required for this bounded
invariant-term unit; a future refresh changes a declared source and
normalization version through review.

Each frozen authority maps to a complete `SourceReference` as follows:

```text
Cboe source_id = cboe-spy-option-terms:2026-08-10
Cboe provider_name = Cboe Global Markets
Cboe dataset_name = S&P Index Options Product Suite Comparison
Cboe provider_record_id = SPDR ETF (SPY)
Cboe provider_request_id = None
Cboe source_symbol = SPY
Cboe source_uri = https://www.cboe.com/tradable-products/product-comparison/

OCC source_id = occ-osi-adjusted-symbol-convention:26853
OCC provider_name = The Options Clearing Corporation
OCC dataset_name = OCC Information Memos
OCC provider_record_id = 26853
OCC provider_request_id = None
OCC source_symbol = None
OCC source_uri = https://infomemo.theocc.com/infomemos?number=26853

both observed_at = 2026-08-10T00:00:00Z
both retrieved_at = 2026-08-10T00:00:00Z
both provider_timezone = None
both origin = provider_reference
both is_delayed = False
both declared_delay_seconds = None
both payload_sha256 = None
both revision_number = None
both provider_correction_id = None
both quality_flags = ()
```

Each `timestamp_methodology` states that UTC midnight is an adapter-assigned
manual verification-date timestamp, not a provider event/publication time.
`TIMESTAMP_ASSIGNED` on the composite metadata discloses that assignment.

The four sources are passed to `NormalizationMetadata`, whose existing
constructor supplies canonical source-ID ordering. The record ID is:

```text
digest = sha256(
    normalization_version + NUL
    + Tiger input reference record_id + NUL
    + provider_identifier + NUL
    + Cboe source_id + NUL
    + OCC source_id
)
record_id = tiger-spy-standard-option-contract: + digest
```

`normalized_at` must be no earlier than all four `retrieved_at` values and the
input Tiger reference's `normalized_at`. The output
`effective_observed_at=max(source.observed_at for all four sources)`.

## Output reference

The returned exact `OptionContractReference`:

- reuses the identical `OptionContractKey` object from the Tiger reference;
- preserves `listing_date=None` and `last_trade_date=None`;
- preserves `deliverable_id=None`, now positively established as the canonical
  standard-deliverable identity by the exact unsuffixed root proof;
- sets only `exercise_style="American"` and
  `settlement_type="Physical"`;
- contains the two unchanged Tiger sources plus the frozen Cboe and OCC
  sources;
- has `record_origin=SYSTEM_COMPOSITE`;
- has exact quality flags `SYMBOL_MAPPED`, `COMPOSITE_SOURCE`, and
  `TIMESTAMP_ASSIGNED` in enum order;
- removes `INCOMPLETE` because the two terms required by the supported cost
  boundary are now authoritative for this exact standard SPY scope; and
- uses a deterministic record ID and normalization version
  `tiger-spy-standard-option-terms-composite-v0.1`.

The effective observation time is the latest `observed_at` across all four
sources, never blindly the Tiger chain receipt time. The methodology explicitly
states which provider supplies identity/multiplier, which authority supplies
invariant product terms and adjusted-root classification, and that no listing
date, last-trade date, quote, analytics, or market-session fact was added.

## Failure precedence

```text
exact argument types
-> intrinsic Tiger verification
-> exact monthly/SPY/ARCX/ETF/USD scope
-> exact standard multiplier and unadjusted key boundary
-> unchanged incomplete Tiger reference and provenance
-> normalized-at chronology
-> frozen Cboe and OCC sources
-> system-composite reference construction
```

Failures expose no credential, account identifier, provider payload, option
chain row, or raw SDK exception.

## Required tests

Synthetic deterministic tests cover:

- exact successful composition, object identity, fields, sources, record ID,
  methodology, version, flags, and chronology;
- multiplier preservation and rejection of non-100/adjusted inputs;
- exact unsuffixed-root acceptance and numeric/alternate-root rejection;
- non-SPY, non-ARCX, non-ETF, non-USD, nonmonthly, conflicting-term, malformed
  source, metadata, and chronology rejection;
- exact Python types, frozen records, direct-construction/tampering resistance,
  public API order, import order, and no package-root re-export;
- effective-observation selection as the exact maximum source observation
  time, including Tiger source times later than the frozen authority captures;
- no SDK import, network, credential, filesystem, environment, wall-clock,
  randomness, or LLM access; and
- successful reuse by the existing cost path with composite-input quality
  propagation, using synthetic quote/Greeks evidence only.

## Explicit exclusions

This unit adds no generic option-terms framework, non-SPY symbol, adjusted or
FLEX contract support, runtime Cboe scraper, current quote, activity, IV,
Greeks, pricing model, dividend/rate logic, relationship binding, report
change, recommendation, account operation, order, or execution behavior.

The real Direct Entry slice remains blocked on authoritative option and
underlying current quotes, activity-session semantics, and usable Gamma/Theta
analytics after this unit.
