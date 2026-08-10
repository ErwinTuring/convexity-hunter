# U.S. Treasury Par-Yield Pricing-Rate Proxy v0.1

## Status and purpose

Formal Tier-A preflight is complete with no unresolved blocker. This contract
freezes one bounded deterministic calculation between the implemented U.S.
Treasury Daily Par Yield Curve adapter and a future pricing producer.

```text
six exact normalized Treasury par-yield points
    -> exact target-tenor match or adjacent calendar-day interpolation
    -> nominal-semiannual to continuous-compounding conversion
    -> one auditable Treasury par-yield pricing proxy plus CalculationLineage
```

This is not an option-pricing engine. It does not produce option values, IV,
Greeks, discount factors, zero rates, OIS rates, SOFR rates, forecasts,
recommendations, or trades. The output is explicitly a bounded MVP proxy made
from the provider-native Treasury par-yield curve; it must never be described
as a bootstrapped risk-free zero curve.

## Public boundary

`convexity_hunter.market_data_transformations` appends exactly these three
direct-module public names:

```text
TreasuryPricingRateInput
TreasuryPricingRateTransformationResult
transform_treasury_pricing_rate
```

Nothing is re-exported from `convexity_hunter.market_data`, the package root,
or a provider package. The provider adapter remains unchanged and no network,
credential, Tiger, report, service, or scenario-pricing behavior is added.

The function signature is:

```python
transform_treasury_pricing_rate(
    calculation_id,
    curve_points,
    target_tenor_days,
    calculated_at,
)
```

The result contains one frozen `TreasuryPricingRateInput` and one existing
`CalculationLineage`.

## Exact input curve

`curve_points` must have exact type `tuple` and contain exactly six exact
`RateCurvePointObservation` objects in this strict tenor order:

```text
30, 45, 60, 90, 120, 180
```

Every point must share these exact declarations from the implemented provider
contract:

```text
curve_id = USD-US-TREASURY-DAILY-PAR-YIELD
currency = USD
compounding_convention = Bond-equivalent yield; simple annualized with semiannual interest convention
day_count_convention = Actual days; 365- or 366-day year
effective_date = one common exact date
record_origin = provider_calculated
normalization_version = us-treasury-daily-par-yield-v0.1
```

Each point must have a distinct nonempty record ID and a nonempty source-ID
tuple. The complete six-point input is retained even when the target exactly
matches one point. Partial curves, duplicates, mixed curves, dates,
conventions, currencies, normalization versions, or constructor-bypassed
records fail closed. This calculation does not recompute provider retrieval,
normalization, correction selection, or freshness. The exact effective date
remains visible for downstream applicability checks.

## Output record

`TreasuryPricingRateInput` is frozen and has these fields in order:

```text
effective_date: date
target_tenor_days: int
source_curve_id: str
currency: str
source_tenors_days: tuple[int, ...]
source_annualized_par_yields: tuple[Decimal, ...]
source_input_references: tuple[CalculationInputReference, ...]
interpolated_annualized_par_yield: Decimal
continuously_compounded_rate_proxy: Decimal
interpolation_methodology: str
compounding_conversion_methodology: str
economic_semantics: str
```

The three source tuples always retain all six values in source-tenor order.
Every retained input reference is independently reconstructed and binds that
tenor and rate to its normalized record ID, normalized time, and complete
nonempty source-ID tuple. The fixed disclosure strings distinguish exact
matching from interpolation and state that the continuous rate is a
calculation proxy derived from a nominal Treasury par yield, not a zero/OIS
curve.

## Tenor selection and interpolation

`target_tenor_days` must have exact type `int` excluding `bool`, and must lie
in the inclusive range 30 through 180. No extrapolation is allowed.

If the target equals a supplied tenor, the selected annualized par yield is
that exact `Decimal` and interpolation methodology is `exact_tenor_match`.
Otherwise the target must be bracketed by the immediately adjacent lower and
upper supplied tenors and precision-34, round-half-even Decimal arithmetic
calculates:

```text
y = y_lower
    + (y_upper - y_lower)
      * (target_days - lower_days)
      / (upper_days - lower_days)
```

The interpolation methodology is
`linear_in_calendar_days_on_provider_native_annualized_par_yields`. It does
not interpolate discount factors, zero rates, instruments, or business-day
maturities. The provider's named-tenor-to-day normalization remains a declared
upstream convention.

## Compounding conversion

The selected or interpolated nominal annualized par yield `y` is converted
under the declared semiannual-interest convention using precision-34,
round-half-even Decimal arithmetic:

```text
r_continuous = 2 * ln(1 + y / 2)
```

The logarithm argument must be finite and strictly positive. Decimal-context
overflow, underflow, invalid operation, division failure, nonfinite
intermediates, and nonfinite results become stable `ValueError` failures. The
caller's complete Decimal context is preserved. Canonical negative zero is
stored as exact positive `Decimal("0")`.

This conversion changes only the quoted compounding convention. It does not
turn a par yield into a zero rate or prove an exact discount factor for the
target maturity.

## Lineage

The exact lineage identity is:

```text
calculation_type = treasury_pricing_rate_proxy
methodology_id = linear-par-yield-tenor-and-continuous-compounding-proxy
methodology_version = v0.1
```

Inputs are exactly the six retained `CalculationInputReference` objects after
the existing `CalculationLineage` constructor's canonical record-ID ordering.
The separate canonical normalized-evidence parameter remains in source-tenor
order and binds each tenor and rate to its exact retained reference. Every
reference independently reproduces the normalized record ID, normalized time,
and complete nonempty source-ID tuple. `calculated_at` is aware UTC after every
input's normalized time. The calculation ID is canonical, differs from every
input record ID, and is not reused as an input.

Canonical parameters retain the exact curve identity, date, source tenors and
rates, target tenor, selected bracket, formula declarations, exact calculated
Decimals, output semantics, and complete normalized-evidence references. They
contain no Python or JSON float.

Quality flags are exactly:

```text
annualized
assumption_applied
```

plus `interpolated` if and only if the target is not an exact source tenor.
`decimal_to_float_converted`, `adjusted_input_used`, `correction_selected`,
`composite_input_used`, and `incomplete_input_used` are prohibited.

## Failure precedence

```text
exact scalar argument types and canonical calculation identity
-> exact curve tuple and exact selected-record types
-> complete six-point curve shape and common provider declarations
-> complete metadata, unique identities, and chronology
-> target range and exact bracket resolution
-> context-independent Decimal interpolation
-> context-independent Decimal compounding conversion
-> output construction
-> complete canonical parameters and lineage
-> immutable result self-verification
```

Failures expose no provider payload, credential, environment value, or raw
exception text.

## Required tests

Focused deterministic tests cover:

- exact 30-, 45-, 60-, 90-, 120-, and 180-day matches;
- independent literal interpolation expectations for EST- and EDT-dated
  curves without treating the date as a session claim;
- positive, zero, and supported negative rates;
- the literal continuous-compounding formula at precision 34;
- exact rejection at 29 and 181 days and no extrapolation;
- partial, reordered, duplicated, mixed-date, mixed-curve, mixed-convention,
  mixed-origin, and mixed-normalization inputs;
- exact Python types, including `bool` rejection;
- logarithm-domain and extreme Decimal failures;
- ambient Decimal precision, rounding, exponent, flags, and trap preservation;
- exact record fields, source tuples, bracket disclosure, lineage inputs,
  canonical parameters, chronology, and quality flags;
- immutable records, direct-construction guards, public API order, both import
  orders, and unchanged `market_data.__all__` and package-root exports; and
- no network, credential, provider SDK, wall-clock, filesystem, environment,
  randomness, or LLM access.

## Explicit exclusions

No bootstrap, curve fit, cubic interpolation, extrapolation, discount factor,
forward rate, zero/spot/OIS/SOFR curve, holiday or business-day inference,
nearest-date fallback, provider routing, cache, pricing engine, IV/Greeks
reconstruction, dividend assumption, scenario generation, report change,
monitor, alert, order, or execution capability is authorized.
