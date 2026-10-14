# Conditional Entry-Fee Research Scenarios v0.1

Status: implemented, independently reviewed and regression tested;
local deployment/real validation recorded in the current checkpoint.
User approval: 2026-10-14. This is research presentation, not a cost upper
bound, confirmed account tariff, execution authority or a classification change.

## Boundary

Keep the existing four required cost components UNKNOWN. Existing premium
budget, sensitivity grid, risk policy, Core formulas and classifications are
unchanged. Missing funding, exit and settlement inputs remain visible.
Conditional scenarios must not enter `CoreCostLedger` as known/bounded fees,
establish affordability/survival, resolve an UNKNOWN or imply underpricing.
Distinguish the existing conditional premium budget from the optional partial
entry subtotal. Neither is total lifecycle cost or maximum loss.

## Declared tariff scenarios

Frozen source: [Hong Kong Futu public US options tariff, sections 4.1–4.3](https://www.futuhk.com/hans/support/topic2_283),
verified 2026-10-14. ORF shown effective 2026-09-01. Use USD and the
published equity-option tariff conditionally; account and product-specific
applicability are NOT_VERIFIED. No promotion, extra service, index surcharge,
currency conversion, rounding rule or future tariff change is inferred.

Assume one buy order per leg, wholly filled within one trading day. A different
order/day pattern is not covered. Display both scenarios in fixed neutral
order; do not choose the user's account package or suggest one package is best:

1. FIXED: platform USD 0.30 per contract.
2. TIER_FIRST_50: platform USD 0.60 per contract, conditional on zero earlier
   monthly contracts and `Q = sum(q_i)` over every leg/order in this scenario
   at most 50 (contract count, never multiplied by contract multiplier).
   Otherwise this
   scenario is unavailable; do not pretend it is the actual tier or extrapolate.

For each leg with exact positive integer quantity `q` and positive indicative
ask `a = CoreLeg.ask_per_underlying_unit` in USD per underlying unit (the
option premium quote unit used by the public USD 0.10 threshold, not the
position premium or per-contract cash amount), conditional commission is
`max(1.99, q*r)`, where `r=0.65` if
`a>0.10`, otherwise `r=0.15`. The indicative ask selects a hypothetical fee
branch only; actual fill premium/fees remain unknown.
Other listed buy-side fees total `q*(0.0122+0.025+0.18+0.0003)`.
Sum commission, platform and other fees over legs, retaining exact unrounded
Decimal arithmetic. Do not include sell-side charges in an entry estimate.
For two one-contract legs, literal golden totals are USD 5.015 (FIXED) and
5.615 (TIER_FIRST_50), irrespective of the commission branch due to its minimum.

Optional partial subtotal = existing `1.10 * indicative position ask basis`
plus scenario entry fees. It explicitly excludes every UNKNOWN lifecycle
component. Missing/invalid asks, unsupported currency or structure leave the
scenario unavailable; do not invent or replace market evidence.

## Presentation and provenance

The Chinese detail report must show scenario assumptions, source URL and
verification date, exact arithmetic, missing components, indicative authority,
unverified applicability/rounding and unestablished survival. No scenario is
a recommendation. Compact output must not rank by scenario or silently claim
that a partial subtotal is affordability evidence.

The implementation must retain scenario policy in a versioned, exact registered
profile and derive presentation from its structured Core record. A renderer
may not apply the new tariff to an old profile or a forged provenance marker.
Historical snapshots/reports remain unchanged; no database migration or
historical recomputation. All three entries use the same shared factory.

## Frozen minimal integration

Read-only preflight found an existing Direct-only fee illustration but no
equity/index discriminator in Core legs. Therefore these are explicitly
conditional public-tariff scenarios, not assertions of security-type or
account applicability. Do not infer security type from symbol syntax or add
a provider lookup just for these scenarios.

Use Standard Research Profile v0.4, adding one closed
`conditional_entry_fee_policy` snapshot. Retain v0.1–v0.3 exact snapshots,
factories, renderer versions and report caches. The new policy snapshot retains
this ID/version, source/date, rates and exact assumptions as fixed values;
there are no user-editable numerical knobs. All other v0.3 policy values remain
unchanged. Economic inputs remain unchanged; versioned profile provenance,
descriptions and methodology labels may identify v0.4.

Reuse existing exact arithmetic and a private structured scenario view derived
from retained Core structure/premium data. Render this view in v0.4 detail
reports for all three entries, including Direct's automatic report. No new
public Core DTO, detail-API field, database schema or persisted prose collection
is required. The existing historical Direct illustration stays separate and
must not be retroactively upgraded. Its legacy scope is not authoritative
product applicability. New scenarios are unavailable when their conditional
input grammar is not satisfied, with a visible reason.

The renderer must match the exact registered request/factory before disclosing
the policy; forged markers cannot authorize a scenario. Snapshot validation
must reject altered values and equality aliases. Core survival and classification
retain their existing outcomes. Where UNKNOWN prevents an upper bound, render
survival as not established, not as a failed or passed numerical test.

## Acceptance

Require literal golden arithmetic, branch/minimum/quantity boundaries,
unavailable-input handling, low Decimal precision independence, exact snapshot
validation, old-profile compatibility and lazy-report/cache version checks.
Prove the four UNKNOWNs and classification/survival results are not upgraded
by either scenario. No new market/model/source calls are needed for BUILD.
An optional new one-shot Direct validation may use already authorized Futu
after review and deployment; it must not replay an old guard or alter archives.

## Validation

Independent review passed after the report explicitly stated the ask unit;
27 focused tests passed. The initial full suite found three obsolete v0.3
version assertions, subsequently corrected. Final full regression passed
2,001 tests in 301.744 seconds. Private-cache compileall, Markdown target/fence
and diff checks passed. The existing urllib3/LibreSSL warning remains; no SDK
or environment workaround was introduced. No live acquisition occurred during
BUILD. Historical v0.3 illustration stays separate; v0.4 reports use the
private structured view, never the Core ledger.
