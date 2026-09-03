# Hunter End-to-End Validation — Sample 6

Date: 2026-09-03

## Scope

This sanitized product record is Sample 6 of the ten-sample aggregate campaign
and the first sample in the separately frozen
[`five-sample extension`](hunter-end-to-end-validation-extension.md). It used
the unchanged
[`Hunter End-to-End Validation Protocol v0.1`](hunter-end-to-end-validation-protocol.md)
and changed no production code, schema, policy, provider boundary, maturity
authority, or discrimination metric.

## Discovery batch and human checkpoint

The bounded public Web Search producer applied
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) to the exact
inclusive source-publication window:

```text
window_start = 2026-06-23
window_end = 2026-06-29
observed_at = 2026-09-02T17:05:00Z
candidate_count = 9
```

This was the next complete unused seven-calendar-day window in the campaign's
frozen reverse-chronological sequence. The production `EventCandidateBatch`
validator passed with neutral earliest-publication/candidate-ID order, no
padding, and no option-market feedback.

The human explicitly selected:

```text
candidate_id = 2026-06-29-explicit-rklb-irdm-merger
selected_discovery_lane = EXPLICIT_CATALYST
willingness_to_continue = yes
event_new_to_human = yes
connection_new_to_human = yes
impact_transmission_credibility = credible
```

The human rejected the other candidates principally because they concerned
completed acquisitions or approvals whose uncertainty had shifted toward
execution, events of unclear enterprise-level materiality, or narrower
listing and index-flow changes. The Rocket Lab/Iridium agreement remained
worth investigating because its approximately USD 8 billion enterprise value,
cash-and-stock consideration, financing, capital-structure, regulatory,
closing, and integration paths directly affect both companies. Financing
terms, approvals, final consideration, leverage, and realized integration
economics remained unresolved.

## Supplemental verification and translation

Translation retained Iridium's source
[`Form 8-K`](https://www.sec.gov/Archives/edgar/data/1418819/000110465926078482/tm2619278d1_8k.htm)
and added only authoritative public filings:

- Rocket Lab's merger
  [`Form 8-K`](https://www.sec.gov/Archives/edgar/data/1819994/000175392626001085/g085783_8k.htm);
- Rocket Lab's August acquisition-progress
  [filing exhibit](https://www.sec.gov/Archives/edgar/data/1819994/000175392626001463/g085846_ex99-2.htm);
- Rocket Lab's
  [`Form 10-Q`](https://www.sec.gov/Archives/edgar/data/1819994/000181999426000062/rklb-20260630.htm)
  for the quarter ended 2026-06-30; and
- Iridium's
  [`Form 10-Q`](https://www.sec.gov/Archives/edgar/data/1418819/000141881926000026/irdm-20260331.htm)
  for the quarter ended 2026-03-31.

The agreement was signed on 2026-06-28 and publicly announced on 2026-06-29.
The provenance-preserving submission retained thirteen fact and interpretation
statements and two distinct hypotheses for `RKLB / XNAS / EQUITY / USD` and
`IRDM / XNAS / EQUITY / USD`. It separated:

- the signed merger, cash and collar-based share consideration, stated
  enterprise value, closing conditions, outside-date and termination paths;
- HSR expiry, the filed but not-yet-effective Form S-4, and filed FCC
  transfer-of-control applications;
- Rocket Lab's committed USD 3.6 billion bridge facility and intended
  permanent debt/equity replacement; and
- Hunter interpretations concerning financing, approval, leverage,
  consideration issuance, closing, integration, network, spectrum, customer,
  and combined-business outcome dispersion.

No complete expected market-impact window was supported:

```text
expected_window = absent
```

The merger agreement supplied an exact future observable milestone, its
initial contractual outside date:

```text
reassessment_by = 2027-06-28
basis_kind = SOURCE_BACKED_MILESTONE
methodology = source-backed-milestone:fact-outside-date:2027-06-28
```

This is only a research-governance point for rechecking transaction status and
the continuing applicability of each hypothesis. It is not an expected close,
impact end, holding period, option-maturity anchor, or forecast. The production
Event Intelligence v0.2 boundary returned:

```text
translation = PASS
status = ACCEPTED
issue_codes = ()
```

The human then explicitly retained only the RKLB acquirer-side hypothesis for
the option-research path. IRDM was not substituted or combined downstream.

## Neutral Browser evidence

At the 2026-09-03 evaluation date, the applicable structural-only RKLB
hypothesis entered the explicit neutral path:

```text
maturity_authority = NEUTRAL_STRUCTURAL_RESEARCH
hypothesis_maturity_alignment = NOT_ESTABLISHED
minimum_expiration = 2026-10-03
maximum_expiration = 2027-01-31
```

The authenticated Futu Browser retained every eligible provider-classified
row. The subsequent mode-compatible discrimination mapping produced:

```text
2026-10-16 = 70 legs / 35 Long Straddles
2026-12-18 = 120 legs / 60 Long Straddles
2027-01-15 = 106 legs / 53 Long Straddles

browser_visible_rows = 296
same_strike_call_put_pairs = 148
```

No expiry was treated as aligned to the merger hypothesis. No contract was
ranked, recommended, default-selected, or labelled with ATM or Delta semantics.

## One-shot RTH discrimination evidence

Exactly one provider-native Browser quote batch was retrieved during valid
U.S. regular trading hours at 2026-09-03 09:32:10 EDT. There was no refresh,
retry, cherry-picking, or multi-batch stitching.

```text
total_legs = 296
ask_side_available_legs = 296
two_sided_available_legs = 267
straddles_with_both_asks = 148
straddles_with_both_legs_two_sided = 119

bid_nonpositive = 29
all_other_quote_reason_codes = 0
```

Probability-Free Convexity Discrimination retained all 148 comparisons in
neutral Browser order. Its reference was the 2026-09-02
`LATEST_COMPLETED_NORMALIZED_CLOSE` of 63.10, not current spot. Authorities
remained:

```text
quote_authority = INDICATIVE_ONLY
payoff_geometry_authority = CONDITIONAL_PROVIDER_STANDARD
exact_deliverable_verification = NOT_ESTABLISHED
hypothesis_maturity_alignment = NOT_ESTABLISHED
quote_reference_temporal_alignment = NOT_ESTABLISHED
cross_structure_quote_synchronicity = NOT_ESTABLISHED
```

## Human option checkpoint and terminal outcome

After reviewing the complete 148-row surface, the human formed one research
preference:

```text
expiration = 2026-10-16
strike = 65
structure = LONG_STRADDLE
call = US.RKLB261016C65000
put = US.RKLB261016P65000

confidently_rejected_count = approximately 142 / 148
search_effort_reduced_vs_raw_browser = yes
preference_possible_without_probability = yes
authority_disclosures_effect = appropriately_constrained
decision_basis = deterministic_geometry
terminal_outcome = OPTION_RESEARCH_PREFERENCE_FORMED
```

`premium/reference` was the first compression variable. The October strikes
60 and 65 shared the surface-low value of approximately 19.18%, materially
below the corresponding later-expiry structures. Conditional 1x and 2x
downside/upside hurdles then distinguished the two: strike 65 required
approximately -16.16%/+22.19% for 1x and -35.34%/+41.36% for 2x, a more
balanced bidirectional geometry than strike 60's approximately
-24.09%/+14.26% and -43.26%/+33.44%. Strike 70 remained comparable, but its
premium/reference rose to approximately 21.63% and its geometry became more
directionally asymmetric. The approximately 5.52% indicative relative spread
was only auxiliary and supplied no formal liquidity conclusion.

The human reported that roughly 142 structures could be rejected confidently.
The serious comparison set was principally October strikes 60, 65, and 70,
plus a few later-expiry strikes near 60 and 65. The 5x/10x hurdles, complete
nine-point response ladder, most far-reference strikes, and exact provider
identifiers did not materially affect the final choice. Multiple hurdles and
the response ladder remained substantially redundant at this surface size;
premium/reference, 1x/2x hurdles, and indicative spread carried most first-pass
human discrimination.

This was not recorded as a mechanical nearest-strike or shortest-expiry
choice. Strike 65 prevailed over strike 60 despite identical minimum
premium/reference because its moderate-move geometry was more bidirectionally
balanced; its lower indicative spread only reinforced that comparison. Later
expiries required substantially more indicative premium without any maturity
authority proving that the extra duration matched the merger path.

## Bounded observation and non-claims

Sample 6 supplies the campaign's second positive option-research preference
among three legitimate comparison surfaces, while preserving the campaign's
no-probability and no-option-feedback rules. On this larger surface,
deterministic geometry reduced 148 structures to a small comparison set and
supported an explicit research preference.

The result does not establish that the selected option is cheap, has positive
expected value, matches the merger timeline, is executable, has complete
deliverable evidence, is formally liquid, or should be traded. It does not
invoke exact-selection verification, Direct Entry, Candidate Assembly,
screening, reporting, position sizing, or trading.

```text
campaign_completed_samples = 6 / 10
extension_completed_samples = 1 / 5
sample_6_terminal_outcome = OPTION_RESEARCH_PREFERENCE_FORMED
```
