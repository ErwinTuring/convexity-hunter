# Hunter End-to-End Validation — Sample 3

Date: 2026-09-02

## Scope

This sanitized product record is Sample 3 of the five-sample campaign frozen
in the
[`Hunter End-to-End Validation Protocol v0.1`](hunter-end-to-end-validation-protocol.md).
It changed no production code, schema, policy, acceptance rule, maturity
authority, provider boundary, or discrimination metric.

## Discovery batch and human checkpoint

The bounded public Web Search producer applied
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) to the exact
inclusive source-publication window:

```text
window_start = 2026-07-14
window_end = 2026-07-20
observed_at = 2026-09-02T10:08:55Z
candidate_count = 9
```

This was the most recent complete unused seven-calendar-day window immediately
before Sample 2. The exact production `EventCandidateBatch` validator passed
with neutral earliest-publication/candidate-ID order, no padding, no option-
market feedback, nine `EXPLICIT_CATALYST` records, and no manufactured records
in the other two lanes.

The human explicitly selected:

```text
candidate_id = 2026-07-16-explicit-tmq-arctic-permitting-schedule
selected_discovery_lane = EXPLICIT_CATALYST
willingness_to_continue = yes
event_new_to_human = yes
connection_new_to_human = yes
impact_transmission_credibility = credible
```

The human rejected the other candidates principally because they were
conventional transactions, post-closing integration cases, or single-product
events whose enterprise-level materiality remained difficult to establish.
TMQ remained worth reviewing because permitting is a direct constraint on
whether a pre-production mining project can progress into financing,
construction, and commercialization, and the public timetable converted an
open-ended uncertainty into observable regulatory stages. The timetable did
not establish approval; litigation, community response, permit conditions,
commodity prices, and financing remained material uncertainties.

## Supplemental verification and translation

Translation retained the selected candidate's SEC-filed announcement and
added only five public authoritative sources:

- the Federal Permitting Dashboard's Arctic Project status and timetable;
- the dashboard's Arctic Project EIS action milestones;
- the federal FAST-41 covered-project disclaimer;
- Trilogy Metals' fiscal-2025 Form 10-K; and
- Trilogy Metals' SEC-filed 2026-08-28 U.S. government investment-agreements
  announcement.

The exact event range was 2026-07-13 through 2026-07-16. The resolved
underlying was `TMQ / XASE / EQUITY / USD`. The ten-statement fact-versus-
interpretation graph retained the published permitting timetable, current
federal review status, non-binding schedule disclaimer, TMQ's 50% Ambler
Metals interest, pre-production project status, financing and third-party
dependencies, and the provisional bidirectional distribution path.

No complete expected market-impact window was supported:

```text
expected_window = absent
```

The federal EIS action page supplied an exact future target for Notice of
Intent issuance and scoping. The caller therefore constructed:

```text
reassessment_by = 2026-09-18
basis_kind = SOURCE_BACKED_MILESTONE
methodology = source-backed-milestone:fact-next-eis-milestone:2026-09-18
```

This is only a research-governance boundary for checking whether the planned
review has begun and the hypothesis remains current. It is not an expected
impact end, permit forecast, holding period, or option-maturity anchor. The
federal source expressly states that planned action dates can change and do
not indicate the final project schedule.

## Event Intelligence and neutral option surface

The production Event Intelligence v0.2 acceptance boundary returned:

```text
status = ACCEPTED
issue_codes = ()
```

At the 2026-09-02 evaluation date, the structural-only hypothesis entered the
explicit neutral path:

```text
maturity_authority = NEUTRAL_STRUCTURAL_RESEARCH
hypothesis_maturity_alignment = NOT_ESTABLISHED
minimum_expiration = 2026-10-02
maximum_expiration = 2027-01-30
```

The authenticated Futu Browser operation for `US.TMQ` returned 48 eligible
provider-classified rows and 24 same-expiration, same-strike Long Straddle
comparisons across:

```text
2026-10-16 = 14 rows / 7 pairs
2026-12-18 = 16 rows / 8 pairs
2027-01-15 = 18 rows / 9 pairs
```

No expiry was treated as aligned with the permitting hypothesis, and no
contract was ranked, recommended, default-selected, or labelled with ATM or
Delta semantics.

## One-shot RTH discrimination evidence

Exactly one provider-native Browser quote batch was retrieved during valid
U.S. regular trading hours at 2026-09-02 09:35:52 EDT. There was no refresh,
retry for better coverage, cherry-picking, or multi-batch stitching.

```text
total_legs = 48
ask_side_available_legs = 48
two_sided_available_legs = 42
straddles_with_both_asks = 24
straddles_with_both_legs_two_sided = 18

bid_nonpositive = 6
all_other_quote_reason_codes = 0
```

Probability-Free Convexity Discrimination retained all 24 comparisons in
neutral Browser order. Its reference was the 2026-09-01
`LATEST_COMPLETED_NORMALIZED_CLOSE` of 3.35, not current spot. Authorities
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

After reviewing the complete 24-row surface, the human selected `NONE` and
reported:

```text
confidently_rejected_count = 24 / 24
search_effort_reduced_vs_raw_browser = yes
preference_possible_without_probability = yes
authority_disclosures_effect = appropriately_constrained
decision_basis = deterministic_geometry
terminal_outcome = OPTION_RESEARCH_NONE
```

`premium/reference` was the primary discrimination variable. The lowest value
on the surface was approximately 34.33%; most structures were above roughly
40% and many were substantially higher. Conditional 1x and 2x downside/upside
hurdles were the second decisive variables. The closest-reference October
structures still combined a high indicative premium/reference burden with
materially asymmetric moderate-move hurdles. The -10%, -20%, -30%, +10%,
+20%, and +30% response ladder confirmed that result.

The 5x/10x hurdles, +/-50% ladder endpoints, exact provider identifiers, and
exact rational notation contributed little to the first-pass decision.
Relative spread was auxiliary. The human found the full ladder and multiple
hurdles partially redundant and judged that premium/reference, 1x/2x hurdles,
and the +/-10%, +/-20%, and +/-30% responses carried most of the useful
human-facing information.

The resulting `NONE` was not an inability to distinguish among similar rows.
The deterministic geometry compressed the surface to the 2026-10-16 strikes
near 3 and 4 for closer review, but neither produced a positive research
preference. This is a valid negative research decision without an event-
probability estimate.

## Bounded observation and non-claims

Sample 3 is the campaign's first natural `OPTION_RESEARCH_NONE` result. It
shows that the existing path can carry a newly selected, source-backed,
accepted hypothesis through a legitimate real option surface and use
probability-free geometry to reject every displayed structure while reducing
search effort.

It does not establish that the options were expensive, lacked positive
expected value, were unsuitable for trading, or could not become interesting
under different evidence. The ask evidence was indicative, the close reference
was non-synchronous, maturity alignment and exact deliverable verification
were not established, and no formal costs or liquidity conclusion was made.

```text
campaign_completed_samples = 3 / 5
sample_3_terminal_outcome = OPTION_RESEARCH_NONE
```
