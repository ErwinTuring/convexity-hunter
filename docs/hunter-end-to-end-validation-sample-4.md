# Hunter End-to-End Validation — Sample 4

Date: 2026-09-03

## Scope

This sanitized product record is Sample 4 of the five-sample campaign frozen
in the
[`Hunter End-to-End Validation Protocol v0.1`](hunter-end-to-end-validation-protocol.md).
It changed no production code, schema, policy, acceptance rule, maturity
authority, provider boundary, or discrimination metric.

## Discovery batch and human checkpoint

The bounded public Web Search producer applied
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) to the exact
inclusive source-publication window:

```text
window_start = 2026-07-07
window_end = 2026-07-13
observed_at = 2026-09-02T14:47:33Z
candidate_count = 10
```

In the campaign's reverse-chronological sequence, this was the most recent
complete unused seven-calendar-day window immediately preceding Sample 3's
2026-07-14 through 2026-07-20 window. The exact production
`EventCandidateBatch` validator passed with neutral earliest-publication/
candidate-ID order, no padding, no option-market feedback, ten
`EXPLICIT_CATALYST` records, and no manufactured records in the other two
lanes.

The human explicitly selected:

```text
candidate_id = 2026-07-09-explicit-plug-gateway-sale-amendment
selected_discovery_lane = EXPLICIT_CATALYST
willingness_to_continue = yes
event_new_to_human = yes
connection_new_to_human = yes
impact_transmission_credibility = credible
```

The human rejected the other candidates principally because they concerned
post-acquisition integration, early clinical or regulatory progress whose
enterprise importance remained difficult to establish, or near-complete
mergers with limited residual outcome dispersion. The PLUG item remained worth
reviewing because staged closing, an extended outside date, fixed sale price,
an additional asset sale, and environmental and repurchase obligations act
directly on a financing-constrained company's balance-sheet and liquidity
path. Final net cash, completion, environmental obligations, and aggregate
liquidity improvement remained unresolved.

## Supplemental verification and translation

Translation retained the selected candidate's
[SEC-filed Form 8-K](https://www.sec.gov/Archives/edgar/data/1093691/000110465926082854/tm2620282d1_8k.htm)
and added only three authoritative public filings:

- the SEC-filed
  [Plug Power property-sale announcement](https://www.sec.gov/Archives/edgar/data/1093691/000110465926082854/tm2620282d1_ex99-1.htm);
- Plug Power's
  [2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/1093691/000110465926022286/plug-20251231x10k.htm); and
- Plug Power's
  [Form 10-Q for the quarter ended 2026-06-30](https://www.sec.gov/Archives/edgar/data/1093691/000110465926093454/plug-20260630x10q.htm).

The exact event range was the 2026-07-09 amendment/report date through the
2026-07-13 detailed public announcement. The resolved underlying was
`PLUG / XNAS / EQUITY / USD`. The fact-versus-interpretation graph retained:

- the Gateway interim-closing framework, fixed USD 142 million full purchase
  price, deposits, 2027-03-31 outside date, restrictions, and repurchase path;
- the separate Texas transaction's initial and contingent consideration;
- the subsequently reported USD 40 million Graham infrastructure closing,
  without treating it as proof of every announced Texas proceeds component;
- reported cash, working capital, recurring losses, negative operating cash
  flows, and financing dependence; and
- the provisional transmission from transaction completion, conditions,
  retained obligations, realized proceeds, and cash use to PLUG's liquidity
  and operating path.

No complete expected market-impact window was supported:

```text
expected_window = absent
```

The contractually stated Gateway outside date supplied one exact future
observable milestone. The caller constructed:

```text
reassessment_by = 2027-03-31
basis_kind = SOURCE_BACKED_MILESTONE
methodology = source-backed-milestone:fact-gateway-amendment:2027-03-31
```

This is only a research-governance boundary for checking transaction status
and whether the hypothesis remains current. It is not an expected impact end,
closing forecast, narrative-duration estimate, holding period, or option-
maturity anchor.

## Event Intelligence and neutral option surface

The production Event Intelligence v0.2 acceptance boundary returned:

```text
status = ACCEPTED
issue_codes = ()
```

At the 2026-09-02 evaluation date, the currently applicable structural-only
hypothesis entered the explicit neutral path:

```text
maturity_authority = NEUTRAL_STRUCTURAL_RESEARCH
hypothesis_maturity_alignment = NOT_ESTABLISHED
minimum_expiration = 2026-10-02
maximum_expiration = 2027-01-30
```

The authenticated Futu Browser operation for `US.PLUG` returned 64 eligible
provider-classified rows and 32 same-expiration, same-strike Long Straddle
comparisons across:

```text
2026-10-16 = 16 rows / 8 pairs
2026-12-18 = 24 rows / 12 pairs
2027-01-15 = 24 rows / 12 pairs
```

No expiry was treated as aligned with the liquidity hypothesis, and no
contract was ranked, recommended, default-selected, or labelled with ATM or
Delta semantics.

## One-shot RTH discrimination evidence

Exactly one provider-native Browser quote batch was retrieved during valid
U.S. regular trading hours at 2026-09-02 11:10:47 EDT. There was no refresh,
retry for better coverage, cherry-picking, or multi-batch stitching.

```text
total_legs = 64
ask_side_available_legs = 64
two_sided_available_legs = 59
straddles_with_both_asks = 32
straddles_with_both_legs_two_sided = 27

bid_nonpositive = 5
all_other_quote_reason_codes = 0
```

Probability-Free Convexity Discrimination retained all 32 comparisons in
neutral Browser order. Its reference was the 2026-09-01
`LATEST_COMPLETED_NORMALIZED_CLOSE` of 2.09, not current spot. Authorities
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

After reviewing the complete 32-row surface, the human formed one research
preference:

```text
expiration = 2026-10-16
strike = 2.0
structure = LONG_STRADDLE
call = US.PLUG261016C2000
put = US.PLUG261016P2000

confidently_rejected_count = approximately 28 / 32
search_effort_reduced_vs_raw_browser = yes
preference_possible_without_probability = yes
authority_disclosures_effect = appropriately_constrained
decision_basis = deterministic_geometry
terminal_outcome = OPTION_RESEARCH_PREFERENCE_FORMED
```

`premium/reference` was the primary discrimination variable. The selected
structure's approximately 21.05% was the lowest value on the surface, below
the adjacent October strikes and the later near-reference structures. Its
conditional 1x downside/upside hurdles were approximately -25.36%/+16.75%,
and its 2x hurdles were approximately -46.41%/+37.80%. These supplied a
relatively interpretable bidirectional geometry alongside the lowest displayed
indicative premium/reference. The approximately 7.06% indicative relative
spread was only auxiliary.

The human reported that the structures requiring serious comparison were
principally October strikes 1.5, 2.0, and 2.5 plus a few later strike-2.0
structures. The 5x/10x hurdles, full response ladder, provider identifiers,
and exact rational notation did not materially affect the choice. Multiple
hurdles and the response ladder remained partly redundant; premium/reference
plus 1x/2x hurdles carried most first-pass cognitive compression.

The selection was not a mechanical nearest-reference or nearest-expiry rule.
Adjacent strikes had higher indicative premium/reference or more directional
geometry, while later strike-2.0 structures required substantially more
indicative premium without any established maturity alignment to justify the
extra duration. This is an explicit human research preference only. The
campaign did not invoke exact-selection verification, Direct Entry, Candidate
Assembly, screening, report generation, position sizing, or trading.

## Bounded observation and non-claims

Sample 4 is the campaign's first natural
`OPTION_RESEARCH_PREFERENCE_FORMED` result. It shows that a newly selected,
source-backed liquidity hypothesis can pass Event Intelligence without an
invented impact end, reach a legitimate neutral real-option surface, and allow
probability-free deterministic geometry to compress 32 structures into one
explicit research preference.

The result does not establish that the structure is cheap, has positive
expected value, matches the transaction timeline, is liquid or executable, is
appropriate for a portfolio, or should be traded. Quotes were indicative,
the close reference was non-synchronous, and maturity alignment, exact
deliverable verification, formal costs, and formal liquidity remained
unestablished.

```text
campaign_completed_samples = 4 / 5
sample_4_terminal_outcome = OPTION_RESEARCH_PREFERENCE_FORMED
```
