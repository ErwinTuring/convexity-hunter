# Hunter End-to-End Validation — Sample 7

Date: 2026-09-05

## Scope

This sanitized product record is Sample 7 of the ten-sample aggregate campaign
and the second sample in the separately frozen
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
window_start = 2026-06-16
window_end = 2026-06-22
observed_at = 2026-09-03T15:57:48Z
candidate_count = 7
```

This was the next complete unused seven-calendar-day window in the campaign's
frozen reverse-chronological sequence. The production `EventCandidateBatch`
validator passed with neutral earliest-publication/candidate-ID order, no
padding, and no option-market feedback. The batch contained five explicit
catalysts, one narrative/belief-shift lead, and one second-order transmission
lead; lane presence was evidence-driven rather than quota-filled.

The human explicitly selected:

```text
candidate_id = 2026-06-17-second-order-clpt-amt130-delivery-path
selected_discovery_lane = SECOND_ORDER_TRANSMISSION
willingness_to_continue = yes
event_new_to_human = yes
connection_new_to_human = yes
impact_transmission_credibility = mixed
```

The human considered the selected lead more discriminating than the batch's
ordinary mergers, approvals, and financing events because the research
question was not uniQure's regulatory progress alone. It was whether the path
from AMT-130 clinical and regulatory progress, through treatment delivery, to
potential demand for ClearPoint navigation and SmartFlow cannulae represented
a real second-order dependency. The human required the connection to fail
closed if primary materials could not confirm actual device use or dependency.
Exclusivity, necessity, per-case economics, future treatment volume, and
enterprise materiality were explicitly not established.

## Supplemental verification and translation

Translation retained uniQure's June regulatory-path
[`Form 8-K exhibit`](https://uniqure.gcs-web.com/static-files/56f8d488-8e00-487f-9336-5bf25eca5e3b)
and added authoritative public materials:

- ClearPoint's 2021
  [AMT-130 trial-use disclosure](https://ir.clearpointneuro.com/news-events/press-releases/detail/1031/clearpoint-neuro-inc-congratulates-uniqure-on-completion),
  which reported use of the ClearPoint Neuro Navigation System and SmartFlow
  MRI-safe cannulae for treated patients in the first U.S. cohort;
- ClearPoint's
  [2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/1285550/000119312526111231/clpt-20251231.htm),
  which describes portfolio-wide dependence of its biologics and drug-delivery
  business on partner clinical, regulatory, and commercial success;
- ClearPoint's
  [August 2026 investor presentation](https://ir.clearpointneuro.com/sec-filings/all-sec-filings/content/0001193125-26-330541/clpt-ex99_2.htm),
  which still lists uniQure/AMT-130 as an active Phase I/II pharma-partner
  program; and
- uniQure's September
  [AMT-130 BLA-submission announcement](https://www.sec.gov/Archives/edgar/data/1590560/000110465926104463/qure-20260902xex99d1.htm),
  which describes targeted MRI-guided delivery and states an intention to
  present four-year data before the end of calendar third quarter 2026.

The submission retained nine fact and interpretation statements for
`CLPT / XNAS / EQUITY / USD`. It separated:

- uniQure's reported June FDA communication and September BLA submission;
- actual historical AMT-130 trial administration using ClearPoint navigation
  and SmartFlow cannulae;
- ClearPoint's current identification of AMT-130 as an active partner program
  and its portfolio-wide business dependency disclosures; and
- the provisional Hunter interpretation that AMT-130 outcomes may alter
  CLPT's support, device-use, and potential commercialization paths without
  establishing direction, magnitude, probability, exclusivity, or economic
  materiality.

No complete expected market-impact window was supported:

```text
expected_window = absent
```

uniQure's stated four-year-data timing supplied an exact future observable
milestone:

```text
reassessment_by = 2026-09-30
basis_kind = SOURCE_BACKED_MILESTONE
methodology = source-backed-milestone:fact-four-year-data-milestone:2026-09-30
```

This is only a research-governance point for reassessing AMT-130 evidence and
the continuing CLPT transmission hypothesis. It is not a predicted impact end,
FDA decision date, holding period, option-maturity anchor, or recommendation.
The production Event Intelligence v0.2 boundary returned:

```text
translation = PASS
status = ACCEPTED
issue_codes = ()
```

The accepted evidence confirms historical trial use plus current partner-
program identification. It does not prove approved-label device requirements,
exclusive or necessary ClearPoint use, every future administration, AMT-130-
specific economics, procedure volume, reimbursement, adoption, or CLPT
enterprise materiality.

## Neutral Browser evidence

At the 2026-09-04 evaluation date, the applicable structural-only CLPT
hypothesis entered the explicit neutral path:

```text
maturity_authority = NEUTRAL_STRUCTURAL_RESEARCH
hypothesis_maturity_alignment = NOT_ESTABLISHED
minimum_expiration = 2026-10-04
maximum_expiration = 2027-02-01
```

The authenticated Futu Browser retained every eligible provider-classified
row. The subsequent mode-compatible discrimination mapping produced:

```text
2026-10-16 = 24 legs / 12 Long Straddles
2026-11-20 = 26 legs / 13 Long Straddles
2027-01-15 = 24 legs / 12 Long Straddles

browser_visible_rows = 74
same_strike_call_put_pairs = 37
```

No expiry was treated as aligned to the AMT-130/CLPT hypothesis. No contract
was ranked, recommended, default-selected, or labelled with ATM or Delta
semantics.

## One-shot RTH discrimination evidence

Exactly one provider-native Browser quote batch was retrieved during valid
U.S. regular trading hours at 2026-09-04 09:59:12 EDT. There was no refresh,
retry, cherry-picking, or multi-batch stitching.

```text
total_legs = 74
ask_side_available_legs = 74
two_sided_available_legs = 60
straddles_with_both_asks = 37
straddles_with_both_legs_two_sided = 23

bid_nonpositive = 14
all_other_quote_reason_codes = 0
```

Probability-Free Convexity Discrimination retained all 37 comparisons in
neutral Browser order. Its reference was the 2026-09-03
`LATEST_COMPLETED_NORMALIZED_CLOSE` of 14.05, not current spot. Authorities
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

After reviewing the complete 37-row surface, the human formed one research
preference:

```text
expiration = 2026-10-16
strike = 15.0
structure = LONG_STRADDLE
call = US.CLPT261016C15000
put = US.CLPT261016P15000

confidently_rejected_count = approximately 33 / 37
search_effort_reduced_vs_raw_browser = yes
preference_possible_without_probability = yes
authority_disclosures_effect = appropriately_constrained
decision_basis = deterministic_geometry
terminal_outcome = OPTION_RESEARCH_PREFERENCE_FORMED
```

`premium/reference` was the first compression variable. October strikes 12.5
and 15.0 formed the principal comparison set at approximately 29.18% and
30.25%, respectively; the corresponding November structures were weaker
alternatives. Strike 15.0 prevailed despite its approximately 1.07 percentage-
point higher premium/reference because its conditional 1x downside/upside
hurdles of approximately -23.49%/+37.01% and 2x hurdles of approximately
-53.74%/+67.26% were more bidirectionally balanced than strike 12.5's
approximately -40.21%/+18.15% and -69.40%/+47.33%. The response ladder only
confirmed that geometry.

The human reported that roughly 33 structures could be rejected confidently.
The serious comparison set was principally October strikes 12.5 and 15.0,
with weaker November equivalents. The 5x/10x hurdles, distant strikes, most
exact provider identifiers, and tail values in the complete response ladder
did not materially affect the final choice. Multiple hurdles and the full
ladder again appeared redundant for first-pass review; premium/reference and
1x/2x hurdles carried most of the decision value.

The approximately 37.76% indicative relative spread on the selected structure
was a material negative warning, not evidence of formal liquidity. It did not
prevent a research preference because the experiment permits spread only as an
auxiliary display metric. A later authoritative liquidity, cost, or
executability assessment could reject the structure. The wording therefore
must not upgrade the result into a tradeable-structure finding.

## Bounded observation and non-claims

Sample 7 is the extension's first selected `SECOND_ORDER_TRANSMISSION` lead and
the campaign's first complete option-research surface reached through that
lane. Primary materials supported a real historical delivery relationship and
current program identification, while preserving the unresolved future
dependency and economic-materiality boundary. Deterministic geometry then
reduced 37 structures to a small comparison set and supported an explicit
research preference without estimating AMT-130 success, CLPT transmission, or
directional probabilities.

The result does not establish that the selected option is cheap, has positive
expected value, matches the AMT-130 timeline, is executable, is formally
liquid, has complete deliverable evidence, or should be traded. It does not
invoke exact-selection verification, Direct Entry, Candidate Assembly,
screening, reporting, position sizing, or trading. In particular, the selected
October expiration remains `NOT_ESTABLISHED` relative to hypothesis maturity.

```text
campaign_completed_samples = 7 / 10
extension_completed_samples = 2 / 5
sample_7_terminal_outcome = OPTION_RESEARCH_PREFERENCE_FORMED
```
