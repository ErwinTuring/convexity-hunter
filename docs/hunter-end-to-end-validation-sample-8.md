# Hunter End-to-End Validation — Sample 8

## Scope and discovery

Sample 8 is the third sample of the frozen five-sample extension. It follows
the unchanged [validation protocol](hunter-end-to-end-validation-protocol.md).
The retrospective publication window was 2026-06-09 through 2026-06-15,
observed at 2026-09-05T15:47:47Z. Eight provisional explicit-catalyst leads
passed the existing batch constructor and producer-policy validation, in
publication-date/candidate-ID order: NUVL, HUMA, ADIL, ELVN, BCRX, DXCM, SNY,
and PAYO. No lane quota, padding, ranking or option feedback was used.
This is not a historical point-in-time backtest or certification of June
events' current status. The attempted independent batch review did not return
a verdict; it must not be described as a completed independent PASS.

The human explicitly selected
`2026-06-10-explicit-huma-v012-interim-offering` for continued research.
Both the event and connection were new to the human; transmission credibility
was `credible`, and the selected lane was `EXPLICIT_CATALYST`.

The human valued the combination of clinical/regulatory progress and financing
dilution: the reported prespecified V012 interim endpoint and cessation of
further enrollment coincided with a roughly USD 50 million offering of about
47.62 million shares. These provide short transmission paths to cash runway,
dilution, regulatory submission and commercialization. Other leads were not
selected because cash mergers were conventional closing/failure branches,
ADIL was already completed, ELVN/BCRX mainly advanced development evidence,
and DXCM/SNY enterprise-level materiality was harder to establish. These are
human research judgments, not system rankings or verified investment claims.

## Translation and temporal evidence

The selected [June prospectus](https://www.sec.gov/Archives/edgar/data/1818382/000110465926072961/tm2616944-3_424b5.htm)
was retained and supplemented by the issuer's
[V012 announcement](https://www.sec.gov/Archives/edgar/data/1818382/000110465926072382/tm2617224d1_ex99-1.htm)
and [August business update](https://www.sec.gov/Archives/edgar/data/1818382/000110465926094440/tm2622949d1_ex99-1.htm).
The update reported aggregate June offering gross proceeds of USD 57.5 million
and continued the second-half-2026 dialysis supplemental-BLA plan. The record
distinguishes the initial offering from that later proceeds update.

Eight fact and interpretation statements produced `HUMA / XNAS / EQUITY / USD`
and `BIDIRECTIONAL_EXPANSION`. The production translation and assessment returned:

```text
translation = PASS
event_intelligence_status = ACCEPTED
issue_codes = ()
expected_window = absent
reassessment_by = 2026-12-31
basis_kind = SOURCE_BACKED_MILESTONE
```

December 31 is the end of the issuer's declared filing period and the point
to reassess submission progress. It is not a forecast of impact duration, an
FDA decision date or a maturity anchor. Issuer-reported clinical results do
not establish independent FDA review, approval, uptake, reimbursement, future
financing sufficiency or enterprise materiality. The human did not separately
rate the naturalness of this reassessment basis; no such rating is inferred.

## Browser and one-shot evidence

At evaluation date 2026-09-08, neutral maturity eligibility was 2026-10-08
through 2027-02-05. Futu exposed 46 legs, exhaustively paired into 23 Long
Straddles: four on 2026-10-16, six on 2026-12-18 and thirteen on 2027-01-15.
No Browser rows were removed for quote or metric availability.

The first sandbox attempt failed during SDK import before provider calls;
the installed SDK was present but encountered a local permission restriction.
The permitted run outside the sandbox succeeded. Exactly one quote batch ran
on 2026-09-08 at 11:48:16 EDT, with provider market-state checks reporting
`AFTERNOON` for HUMA and the checked listed option. This operational RTH check
does not establish quote-frame session binding. There was no quote refresh.

```text
ask_side_available_legs = 46 / 46
two_sided_available_legs = 20 / 46
straddles_with_both_asks = 23 / 23
straddles_with_both_legs_two_sided = 4 / 23
bid_nonpositive = 26
all_other_quote_reason_codes = 0
reference_basis = LATEST_COMPLETED_NORMALIZED_CLOSE
reference_session = 2026-09-04
reference_close = 0.6049
```

The complete 23-row primary comparison table was displayed in conversation,
in neutral Browser order, with premium/reference, 1x/2x/5x/10x hurdles and
indicative spread. Exact identifiers, rational values and the full response
ladder were retained in an external local artifact. Raw payloads were not
committed. The reference is a completed daily close, not synchronized spot.
All authorities remained:

```text
quote_authority = INDICATIVE_ONLY
payoff_geometry_authority = CONDITIONAL_PROVIDER_STANDARD
exact_deliverable_verification = NOT_ESTABLISHED
hypothesis_maturity_alignment = NOT_ESTABLISHED
quote_reference_temporal_alignment = NOT_ESTABLISHED
cross_structure_quote_synchronicity = NOT_ESTABLISHED
```

## Human checkpoint and outcome

```text
human_structure_selection = NONE
confidently_rejected_count = 23 / 23
search_effort_reduced_vs_raw_browser = yes
preference_possible_without_probability = yes
missing_spread_blocked_judgment = no
authority_disclosures_effect = appropriately_constrained
decision_basis = deterministic_geometry
terminal_outcome = OPTION_RESEARCH_NONE
```

Premium/reference was decisive: the lowest displayed ratio was approximately
99.19% at October strike 0.5; December and January strike 1.0 were approximately
132.25% and 123.99%. The 1x/2x hurdles confirmed the human's rejection through
large required moves and absent or extreme downside branches. No local set of
structures warranted further balancing in the human's judgment.

The human mostly ignored 5x/10x, the response ladder, identifiers and exact
fractions after the first metrics had resolved the decision. Spread was
auxiliary and its absence did not block judgment. Repeated hurdle/ladder
information again appeared redundant; emphasizing premium/reference and
1x/2x with other details available on demand is retained as feedback only.
No presentation contract or metric was changed during the campaign.

The human explicitly described this as useful negative compression, not an
inability to judge: all 23 structures were rejected within the displayed
conditional geometry without estimating clinical, regulatory or price
probabilities. This supports the usefulness of discrimination for this sample;
it does not prove overpricing, negative expected return, untradeability or
investment value. No exact selection, Direct Entry, screening or trading ran.

Eight of ten aggregate samples and three of five extension samples are now
complete. Samples 9 and 10 remain; aggregate synthesis waits until Sample 10.
