# Hunter End-to-End Validation — Sample 10

## Discovery and translation

The final sample of the [frozen extension](hunter-end-to-end-validation-extension.md)
used publication window 2026-05-26 through 2026-06-01, observed at
2026-09-09T00:13:13Z. Five candidates passed the existing batch/policy checks:
PODD, IREN, MYRG, TDAC and IMMP in publication-date/ID order. Four were explicit
catalysts and IREN was `NARRATIVE_BELIEF_SHIFT`. No option feedback or ranking
was used. This was retrospective discovery, not a point-in-time backtest.

The human selected `2026-05-26-narrative-iren-gpu-contract-financing`.
Event and connection novelty were both yes/high. Credibility was `MIXED`:
mechanism credible, enterprise-level magnitude unestablished. The new chain
was customer contract -> assets/deployment -> project financing -> acceptance
and cash flow -> debt obligations/limited guarantees, rather than AI demand
implying revenue growth. PODD's impact scale, MYRG's conventional integration,
TDAC's mixed technical/SPAC uncertainties and IMMP's correlational evidence
were less compelling to this human; these are not system rankings.

The retained [Dell procurement announcement](https://www.sec.gov/Archives/edgar/data/1878848/000187884826000030/irentrgts44bninarrwithbl.htm)
and [Microsoft-deployment financing disclosure](https://www.sec.gov/Archives/edgar/data/1878848/000114036126023427/ef20075181_8k.htm)
concern distinct deployments. The approximately USD 1.6 billion procurement
and USD 3.6 billion financing must not be treated as one arrangement.
Supplemental [annual-report evidence](https://www.sec.gov/Archives/edgar/data/1878848/000187884826000052/iren-20260630.htm)
retained conditional commitments, escrow and partial funding, not guaranteed
future revenue, utilization or unrestricted cash.

Seven sourced fact/interpretation statements produced translation PASS and
Event Intelligence `ACCEPTED`, with no issues, for IREN/XNAS/EQUITY/USD and
`BIDIRECTIONAL_EXPANSION`. `expected_window` remained absent. Reassessment
used the source-backed contractual availability endpoint `2027-05-29`.
The human rated this natural but coarse: a mandatory latest-review checkpoint,
not validity guaranteed until that date, predicted narrative duration or
maturity anchor. Earlier material changes may require fresh reassessment;
no automatic extension was authorized.

## One-shot market exercise

Evaluation date 2026-09-09 gave neutral eligibility 2026-10-09 through
2027-02-06. Browser retained 380 legs and 190 same-strike Long Straddles:
51 October 16, 51 November 20, 50 December 18 and 38 January 15.

Exactly one quote batch ran at 2026-09-09 09:44:21 EDT. The wall clock was
inside regular hours and Futu's market-state query returned `AFTERNOON` for
the underlying and checked option. That provider label is retained literally,
not interpreted as a canonical quote-frame session timestamp. No refresh or
quote retry ran.

```text
ask_side_available_legs = 380 / 380
two_sided_available_legs = 377 / 380
straddles_with_both_asks = 190 / 190
straddles_with_both_legs_two_sided = 187 / 190
bid_nonpositive = 3
all_other_quote_reason_codes = 0
non_comparison_rows = 0
reference = LATEST_COMPLETED_NORMALIZED_CLOSE
reference_session = 2026-09-08
reference_close = 46.93
```

All 190 primary comparison rows and full audit sections were provided in a
linked local document in neutral order; the subsequent human feedback cited
specific rows and ladder values. No raw payload was committed. Quote authority
remained `INDICATIVE_ONLY`, geometry `CONDITIONAL_PROVIDER_STANDARD`, maturity
authority `NEUTRAL_STRUCTURAL_RESEARCH`. Exact deliverable verification,
hypothesis maturity alignment, quote/reference temporal alignment and
cross-structure synchronicity all remained `NOT_ESTABLISHED`.

## Human option checkpoint

```text
selection = 2026-10-16 / 47.0 / LONG_STRADDLE
call = US.IREN261016C47000
put = US.IREN261016P47000
confidently_rejected_count = approximately 175 / 190
search_effort_reduced_vs_raw_browser = YES, MATERIAL
preference_possible_without_probability = YES
authority_disclosures_effect = POSITIVE, constraining
decision_basis = deterministic_geometry
terminal_outcome = OPTION_RESEARCH_PREFERENCE_FORMED
```

The rejection estimate was not a checklist count; approximately 10--15
structures received serious comparison. The human prioritized 1x/2x symmetry,
premium/reference, representative +/-10/20/30% responses, cross-expiry
geometry, missing maturity alignment and complete two-sided evidence.

At October strike 47, premium/reference was 22.2672%, 1x hurdles
-22.1180%/+22.4164%, and 2x -44.3853%/+44.6836%. Strikes 45 and 46 had lower
premium/reference (21.8410% and 22.0541%) but less symmetric hurdles. The human
accepted a small added premium burden for symmetry rather than selecting the
lowest premium. Multiple shock responses confirmed the symmetry. For strike
47, November/December/January premium/reference rose to approximately
33.24%/38.67%/43.36%; the human did not assign extra narrative-alignment value
to those tenors. This does not prove extra time has no economic value.

The 4.4010% indicative spread was auxiliary, not the narrowest-spread choice
or formal liquidity evidence. The human largely ignored 5x/10x, distant-strike
ladder detail and exact IDs. Hurdles and the full ladder were redundant for
first-pass comparison; compact primary metrics plus full audit detail is a
product question, not an implemented change.

The preference does not prove nearest-reference heuristics irrelevant: symmetry
and proximity are mechanically related. It records the human's explicit
comparison reasoning, not independent proof of a distinct selection algorithm.
No exact verification, Direct Entry, Candidate Assembly, screening or trading
followed. The ten-sample campaign is complete; see the
[ten-sample synthesis](hunter-end-to-end-validation-ten-sample-synthesis.md).
