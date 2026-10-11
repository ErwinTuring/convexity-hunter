# Core Cash and Sensitivity Research Policy v0.1

Status: Implemented; independent review, 87 focused tests, 1,944 full-suite
tests and local deployment verification passed.
Approval date: 2026-10-11. Applies to all three entries through the shared Core
request factory. This is research authority, not trading authorization.

## Approved numerical assumptions

- Observed position ask basis: sum of each leg's indicative ask multiplied by
  its exact quantity and multiplier. No executable-price or timing upgrade.
- Conditional premium budget: 1.10 times that observed position ask basis.
  This is a declared research budget, not a market-price upper bound, slippage
  prediction, fill guarantee, or total-cost bound.
- For a supported same-strike Long Straddle, let K be its strike and A0 the
  sum of baseline per-underlying-unit asks. Terminal test prices are
  K + x*A0 for x in (-2, -1, 0, 1, 2), in this neutral order.
- Each test price is crossed with per-leg ask factors (1, 1.10, 1.25), in
  this order. Terminal prices remain anchored to baseline A0, not stressed
  asks. The 1.25 factor does not increase the 1.10 premium budget.
- A negative terminal price is explicitly not applicable. It is never
  clamped to zero, substituted, or silently dropped from the disclosed grid.

The factors and grid are approved research assumptions, not empirical market
bounds, probability forecasts, or constants attributed to Taleb. Existing
portfolio, quantity, single-loss and repeat-loss policy remain unchanged.

## Cash and strategy boundary

Applicable broker/exchange fees require the actual account's authoritative
tariff or an explicit evidenced bound. Unknown costs remain unknown, never zero.
The approval does not assert cash-only funding, an early-exit strategy, zero
financing, no exercise/settlement costs, or a broker/account fee schedule.
Only an explicitly declared strategy may make a cost inapplicable.

The premium budget plus all applicable evidenced cost bounds may support a
conditional total cash/loss bound. It is not actual transaction cost or an
unqualified loss bound following physical exercise into stock positions.
Unknown required costs retain DATA_INSUFFICIENT_CORE. No approval here supplies
actual tariff evidence or establishes exact deliverable terms.

## Output boundary

Retain baseline asks, quantity/multiplier, policy version, assumptions and
unknown components. Show the complete neutral grid and conditional expiration
payoff/hurdles. A gross 1x value is not a net-profit multiple or formal
break-even. No early-exit value, Theta-times-days, IV inference, probability,
expected return, score, ranking, automatic recommendation or trading.

Sensitivity is descriptive; the approval does not add a sensitivity threshold
to the Core classification. Optional historical valuation remains optional.
Historical records must retain their original policy and numerical results;
reading or rendering them must not silently apply this successor policy.

## Frozen integration and compatibility

Read-only preflight confirms the shared Host request factory already supplies
all three entries, and the Core already accepts explicit cost and sensitivity
records. No new economic estimator or Core numeric DTO is required.

Introduce Standard Research Profile v0.2 as the normal successor, attaching
this policy in the immutable profile snapshot and request provenance. Preserve
the exact v0.1 snapshot and its historical no-ledger/no-sensitivity factory
behavior. Store validation accepts only the two registered exact snapshots;
unknown versions or altered numerical parameters remain rejected. Reading old
records does not evaluate them under v0.2. No database schema migration.
The bounded preflight returned READY. Main selected a versioned profile
snapshot rather than a new archive metadata field: the existing snapshot and
request provenance already carry the successor policy without widening DTOs.
Report caches retain their renderer version; a successor renderer must remain
able to read historical caches without claiming they used the new policy.

For v0.2, valid supported structures with all required positive indicative asks
receive the 1.10 conditional premium budget. Required cost categories are
entry fees and strategy-dependent funding/exit/settlement costs, explicitly
UNKNOWN until applicable strategy and authoritative bounds are supplied.
No numerical tariff or cash-funding assumption has been authorized here.

The approved sensitivity grid applies only to the supported equal-quantity,
equal-multiplier same-strike/same-expiration Long Straddle grammar. Single-leg
and unsupported structures retain their sensitivity gap; do not silently
extend the straddle example into a new policy. Missing asks retain their gaps.

Negative grid points cannot enter the existing nonnegative numeric DTO; retain
them explicitly as not-applicable in the policy/grid description and Chinese
report, while numerical results consume only valid nonnegative points. This
does not change the Core DTO or clamp prices. All skipped point identities and
original negative values remain auditable in the retained description.

Chinese reporting exposes the budget assumption, unknown cost categories,
fixed-baseline grid and stress factors without overwriting historical report
semantics. Sensitivity is not a new hard classification gate. Existing
hold-period inputs never become early-exit price or P&L calculations.

BUILD scope: Host profile/factory, exact historical profile validation,
conditional policy disclosure in the existing renderer, focused tests and
current state documentation. Independent review and regression are required
before commit. No live quote refresh or market/source/model acquisition.

## Validation and remaining inputs

Independent review found and resolved a cross-version provenance boundary:
v0.2 archives require the exact registered factory request; v0.1 preserves
historically valid unmarked custom requests but rejects registered successor
provenance. The renderer only discloses v0.2 after full request/factory matching.
Historical report caches retain their original renderer version. Snapshot
validation rejects Boolean/integer and float/integer equality aliases.

Focused validation: 87 tests passed. The first full regression found three
obsolete Direct tests expecting the normal factory to omit its cost ledger;
these expectations were updated to the approved v0.2 behavior, without changing
production behavior to satisfy them. Final regression: 1,944 tests passed in
297.785 seconds; compileall and documentation/link/fence checks passed.
The environment emitted its existing urllib3/LibreSSL compatibility warning.
No production changes were made to suppress it.

The local workbench was gracefully restarted with the same durable database.
Read-only HTTP verification returned Host/journal/UI READY, three configured
executors, Profile v0.2 and cash/sensitivity policy v0.1. The one retained
historical Direct case remained readable and its report SHA-256 was unchanged.
Configuration is not proof that fresh Event/World research succeeds. No POST,
new quote batch, model request or source request was used for this verification.

Tariff applicability remains a separate input. Public Hong Kong Futu
[combination-order guidance](https://www.futuhk.com/hans/support/topic2_750from_platform%3D4%26lang%3Den-us)
states that each leg is charged separately and minimum charges apply per leg.
This does not establish a user's actual package, promotional entitlement,
future fill venue or strategy-dependent charges. No tariff numbers or private
account details were added to the profile. Unknown costs remain unknown.

### Public tariff evidence — 2026-10-11

Fresh verification for final MVP closure confirmed the rates below against
the official [tariff sections 4.1–4.3](https://www.futuhk.com/hans/support/topic2_283from_platform%3D2%26%26lang%3Dzh-hk).
Buy-side illustrations assume USD US equity options, one order per leg
executed within one trading day, and no promotion or additional service.
Separate trading-day executions are billed as separate orders. The public
page does not establish option-fee rounding; retain unrounded arithmetic and
mark rounding UNKNOWN. Do not identify the actual account package from the
broker's default-package description.

Fixed platform pricing and the published first-50-contract tier may be
displayed as separate conditional scenarios, not selected as the account's
tariff. Sell-side SEC fees depend on eventual transaction proceeds; no future
closing price or exit-fee total is inferred. Entry settlement charges in this
tariff are not evidence that physical exercise/stock conversion is safe.
The subsequently approved strategy governance is in
[strategy v0.1](core-strategy-governance-v0.1.md); the earlier approval-only
statements above remain historical, not a denial of that later approval.

The [Hong Kong Futu public options tariff](https://www.futuhk.com/hans/support/topic2_283from_platform%3D1%26%26lang%3Dzh-hk)
lists USD 1.99 minimum commission per leg/order, fixed platform fee 0.30 per
contract, and a tiered alternative from 0.60 to 0.05. Listed per-contract
third-party charges are ORF 0.0122, clearing 0.025, settlement 0.18 and CAT
0.0003. ORF is stated effective 2026-09-01; sell-side charges are separate.

For one contract per leg, fixed pricing, one buy order per leg and the listed
standard tariff, the unrounded entry-fee arithmetic is
`2 * (1.99 + 0.30 + 0.0122 + 0.025 + 0.18 + 0.0003) = 5.015 USD`.
This is a conditional published-tariff illustration, not a confirmed debit,
rounding rule, actual account tariff or cost upper bound. Multi-day execution,
applicable package, funding, closing/abandonment and exercise prevention remain
explicit unresolved inputs. The production profile still uses UNKNOWN and
does not consume this illustration. No cash-only or no-exercise policy has
been presumed.
