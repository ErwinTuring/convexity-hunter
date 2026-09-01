# Probability-Free Convexity Discrimination Real Experiment

Date: 2026-09-01

## Scope and question

This sanitized product checkpoint records the first bounded positive real-
product evidence for
[`Probability-Free Convexity Discrimination v0.1`](probability-free-convexity-discrimination-v0.1-contract.md).
It asked whether deterministic payoff geometry materially improves a human's
ability to discriminate across one real NDAQ neutral-structural option surface
without probability, ranking, recommendation, or hidden maturity claims.

This was a product exercise, not a BUILD. It changed no production contract,
calculation, provider boundary, Candidate path, screening result, or historical
exercise.

## One-batch protocol and coverage

During valid U.S. regular option hours, the repository-external experiment:

1. retained the existing NDAQ `NEUTRAL_STRUCTURAL_RESEARCH` Browser and
   `NOT_ESTABLISHED` hypothesis-maturity alignment;
2. obtained exactly one fresh Futu Browser quote batch, with no refresh,
   retry for better coverage, cherry-picking, or multi-batch stitching;
3. retained all 164 Browser legs and all 82 same-expiration, same-strike Long
   Straddle comparisons in neutral Browser order; and
4. used the latest completed normalized NDAQ close, 98.61 for the 2026-08-31
   session, as the declared reference rather than current spot.

Sanitized coverage was:

```text
option legs: 164
Long Straddle comparisons: 82
ask-side available legs: 164 / 164
two-sided available legs: 135 / 164
Straddles with both asks available: 82 / 82
Straddles with both legs two-sided: 53 / 82
```

The complete comparison surface was persisted outside the repository and
verified before human presentation. No raw Futu payload, credential, account
identifier, private configuration, or unsanitized provider output is retained
here.

## Authority boundary

Every comparison retained:

```text
quote_authority = INDICATIVE_ONLY
payoff_geometry_authority = CONDITIONAL_PROVIDER_STANDARD
exact_deliverable_verification = NOT_ESTABLISHED
hypothesis_maturity_alignment = NOT_ESTABLISHED
quote_reference_temporal_alignment = NOT_ESTABLISHED
cross_structure_quote_synchronicity = NOT_ESTABLISHED
```

Premium/reference and conditional hurdles are deterministic geometry relative
to the declared latest completed close and indicative ask basis. They establish
no event probability, expected return, quote executability, formal liquidity,
contract affordability, maximum loss, correct maturity, or investment merit.

## Blind human selection

Before selection, the historical Browser-only NDAQ structure was neither
surfaced nor used as a reference. After reviewing all 82 comparisons, the human
selected:

```text
structure: LONG_STRADDLE
expiration: 2026-10-16
strike: 97.5
Call: US.NDAQ261016C97500
Put: US.NDAQ261016P97500
```

Relevant indicative geometry was:

```text
premium/reference: approximately 8.0114%
1x hurdles: approximately -9.14% / +6.89%
2x hurdles: approximately -17.15% / +14.90%
relative spread: approximately 20.98%
```

The human reported that premium/reference supplied the strongest compression
variable, multiple hurdles supplied the main second-stage explanation, and
relative spread was secondary. The response ladder's detailed values were
mostly ignored because they overlapped with the multiple hurdles. Exact
fraction-heavy presentation reduced readability; approximate percentages were
more useful for human comparison.

The human estimated that approximately 65--70 of 82 structures could be
confidently rejected, reported that search effort was materially reduced
relative to the raw Browser, and formed a research preference without a
probability estimate. The decision basis was deterministic payoff geometry,
not an expiry/strike heuristic. Authority disclosures were assessed as
appropriately constraining, particularly because `NOT_ESTABLISHED` maturity
alignment prevented the expiration from being interpreted as narrative-
duration matching.

## Historical Browser-only comparison

The prior neutral Browser exercise had selected the middle visible expiration
and that expiration's median strike solely for experiment design:

```text
2026-12-18 85 LONG_STRADDLE
```

Its geometry on the Experiment D surface was approximately:

```text
premium/reference: 18.5580%
1x hurdles: -32.36% / +4.76%
2x hurdles: -50.92% / +23.31%
relative spread: 21.48%
```

The new blind selection therefore changed the human choice rather than merely
making the historical choice easier to explain.

## Bounded conclusion

```text
implementation_status = IMPLEMENTED_AND_REVIEWED
real_product_value_evidence = POSITIVE_BOUNDED
```

`POSITIVE_BOUNDED` means only that one real NDAQ option surface demonstrated
material human research-space compression. It does not establish repeatability,
investment attractiveness, cheapness, positive expected value, tail-event
probability, correct maturity, exact deliverable, formal liquidity,
synchronized quotes, executable prices, or recommendation quality.

No exact-contract verification, Direct Entry, Candidate Assembly, screening,
reporting, position sizing, execution, or trading followed this experiment.
