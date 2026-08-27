# Neutral Structural Research Real Exercise

## Scope

On 2026-08-27, one repository-external bounded Web Search run applied
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) to the new
inclusive source-publication window 2026-08-20 through 2026-08-26. It produced
eight validated `EventCandidate` records in neutral source-date and candidate-ID
order, with no padding, score, recommendation, or automatic promotion.

The user explicitly selected:

```text
2026-08-25-narrative-nasdaq-always-on-markets
```

The event and the event-to-underlying connection were both new to the user.
The user assessed the impact/transmission credibility as mixed and explicitly
continued with the selected item, recording willingness to research it. Its
discovery lane was `NARRATIVE_BELIEF_SHIFT`. Batch-level rejection reasons for
the other seven discovery candidates were not separately supplied, so none are
inferred here. No historical NVDA or IONQ submission was modified or
reclassified.

## Translation and temporal authority

After selection, source-supported supplemental verification added
[SEC Release No. 34-105199](https://www.sec.gov/files/rules/sro/nasdaq/2026/34-105199.pdf)
to the selected Nasdaq source. Candidate-to-submission translation retained
that provenance without completing or repairing fields. The caller then built
the structural-only NDAQ submission, and a separate Event Intelligence
assessment returned:

```text
expected_window: absent
distribution mode: BIDIRECTIONAL_EXPANSION
reassessment basis: SOURCE_BACKED_MILESTONE
reassessment_by: 2027-10-10
Event Intelligence: ACCEPTED
acceptance issues: none
```

The retained observed fact
`fact-sec-night-session-milestone-2027-10-10` links to that SEC release and
states the exact 2027-10-10 milestone. The SEC issued the approval order on
2026-04-10. The order requires Nasdaq to make a further Night Session readiness
filing before operation and to file to remove the Night Session rules if the
readiness filing is not made within 18 calendar months. Deterministic calendar
arithmetic therefore supplies the exact source-backed reassessment boundary;
the methodology retains the observed-fact identifier and date.

`reassessment_by` answers when the hypothesis must be revalidated. It is not a
predicted impact end, narrative-duration estimate, holding-period input, or
option-maturity anchor. The user assessed this basis as natural because it
preserves that distinction without hidden duration prediction.

## Neutral Browser

At the 2026-08-27 evaluation date, the accepted structural hypothesis entered
option discovery only through:

```text
OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH
minimum expiration: 2026-09-26
maximum expiration: 2027-01-24
hypothesis_maturity_alignment: NOT_ESTABLISHED
```

The real Futu Browser exposed all 162 provider-classified eligible contracts,
or 81 same-strike Call/Put pairs:

| Expiration | Contracts | Same-strike pairs |
| --- | ---: | ---: |
| 2026-10-16 | 38 | 19 |
| 2026-12-18 | 58 | 29 |
| 2027-01-15 | 66 | 33 |

The Browser performed no ranking, default selection, ATM/Delta inference,
quote use, or liquidity qualification. The user assessed its usefulness as
mixed: it supplied a legitimate real-contract research surface, but almost no
lawful information for narrowing 162 contracts by research relevance.

## Explicit structure and Direct Entry result

The user explicitly selected the middle visible expiration and that
expiration's median strike solely as neutral experiment design:

```text
structure: LONG_STRADDLE
expiration: 2026-12-18
strike: 85
Call: US.NDAQ261218C85000 x 1
Put:  US.NDAQ261218P85000 x 1
assumed portfolio value: USD 10,000
expected holding period: 30 calendar days
```

The selection did not use or claim ATM, Delta, IV, quote, liquidity, expected
return, attractiveness, recommendation, or alignment to narrative duration.
The user made no economic rejection of the other rows because the evidence
needed to distinguish them remained absent.

Both selected Browser rows were retained by identity. Futu exact verification
confirmed each exact identifier, expiration, strike, option type, provider
`MONTH`, provider `STANDARD`, American exercise type, and multiplier 100. No
contract was substituted. `STANDARD` remained a provider classification and
both provider-neutral contract references retained `INCOMPLETE`; no exact
deliverable status was inferred.

The existing Direct Entry and offline single-structure paths then returned:

```text
Futu exact leg verifications: 2 PASS
Browser-selection bridge exact gate: PASS
Direct Entry exact gate: PASS
research-readiness verification: absent
caller-supplied candidate state: DATA_INSUFFICIENT
independently produced screening state: DATA_INSUFFICIENT
position-management plan: absent
```

The deterministic screening reasons remained the frozen six gaps:

```text
missing_costs
missing_liquidity
missing_volatility_environment
missing_structure_expiration_tail_slice
missing_target_move_scenario
missing_volatility_crush_scenario
```

The Chinese report retained the exact maturity sidecar through every boundary
and rendered:

```text
hypothesis_maturity_alignment = NOT_ESTABLISHED
maturity authority = NEUTRAL_STRUCTURAL_RESEARCH
```

It explicitly stated that the expiration entered research only because it was
inside the neutral 30--150 DTE interval and was selected by the user, and that
no alignment to narrative duration or expected impact was established. The
user assessed this disclosure as understandable and honest.

## Product conclusion

This exercise positively validates one bounded claim:

> An accepted structural narrative can enter a real human-selected option
> research loop without inventing an expected impact end, while
> `NOT_ESTABLISHED` maturity alignment survives to the final Chinese report.

It does **not** validate convexity-opportunity discovery, relative structure
quality, or investment value. The selected exact structure was useful for the
closure experiment, but its economic research state remained honestly
`DATA_INSUFFICIENT`.

The next product question is bounded and separate:

> How can the Browser improve human research discrimination without ranking,
> recommending, importing market-data qualification, or hiding a maturity-
> duration prediction?

This question does not automatically unfreeze the six `missing_*` work units.
No credential, account identifier, raw provider payload, or secret was
persisted. No trading call was made. Focused validation passed 212 tests; the
full suite passed 1,348 tests, and compileall plus `git diff --check` passed.
