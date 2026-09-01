# Hunter End-to-End Validation — Sample 1

Date: 2026-09-02

## Scope

This sanitized product record is Sample 1 of the five-sample campaign frozen
in the
[`Hunter End-to-End Validation Protocol v0.1`](hunter-end-to-end-validation-protocol.md).
It changed no production code, schema, policy, acceptance rule, maturity
authority, provider boundary, or discrimination metric.

## Discovery batch and human checkpoint

The bounded public Web Search producer applied
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) to the exact
inclusive source-publication window:

```text
window_start = 2026-08-27
window_end = 2026-09-02
observed_at = 2026-09-01T22:46:15Z
candidate_count = 10
```

The validated batch retained all three policy lanes, neutral
earliest-publication/candidate-ID order, at most ten source-backed candidates,
no padding, and no option-market feedback. The human explicitly selected:

```text
candidate_id = 2026-08-31-explicit-amzn-ad-auction-lawsuit
selected_discovery_lane = EXPLICIT_CATALYST
willingness_to_continue = yes
event_new_to_human = yes
connection_new_to_human = no
impact_transmission_credibility = credible
```

The human rejected the other candidates principally because their likely
importance to large parent companies appeared weak, their approval or
settlement had already occurred with limited residual distribution change, or
their second-order transmission was too long or depended on non-binding early
signals. The AMZN item remained worth reviewing because adjudication and
remedy were open and the alleged conduct directly concerned advertising-auction
pricing, advertiser behavior, and platform economics. The principal
uncertainties remained the legal outcome and materiality to Amazon as a whole.

## Supplemental verification and translation

The candidate-to-submission translation retained the two exact candidate
sources and added only three public authoritative sources:

- the [FTC Amazon case page](https://www.ftc.gov/legal-library/browse/cases-proceedings/amazon),
  which reported `Pending` status and only the 2026-08-31 filing timeline item;
- the [filed complaint](https://www.ftc.gov/system/files/ftc_gov/pdf/AmazonAds-Complaint.pdf),
  which stated the allegations and requested relief; and
- Amazon's [Form 10-Q for the quarter ended 2026-06-30](https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm),
  which supplied source-backed advertising-services business context.

The exact event date remained the complaint filing date, 2026-08-31. The
resolved underlying was `AMZN / XNAS / EQUITY / USD`. Facts, interpretation,
contradiction, uncertainties, and falsification conditions were complete. The
hypothesis remained a provisional `BIDIRECTIONAL_EXPANSION` interpretation:
open legal and remedial outcomes could transmit through auction-mechanism
changes, monetary relief, advertiser behavior, trust, and advertising
economics, without establishing direction, probability, or enterprise
materiality.

No retained source supplied an expected market-impact end or an exact future
procedural milestone. Translation therefore preserved:

```text
expected_window = absent
reassessment = absent
```

No litigation-duration estimate, generic governance deadline, option expiry,
or holding period was introduced to make the submission pass.

## Event Intelligence result

The production Event Intelligence v0.2 acceptance boundary returned:

```text
status = INCOMPLETE
issue_code = missing_temporal_applicability
subject_id = hypothesis-amzn-ad-auction-litigation
terminal_outcome = EI_NOT_ACCEPTED
```

This is a semantic product result, not an operational failure. Discovery
created explicit human research interest and the source-backed AMZN mapping and
impact path survived translation, but the hypothesis lacked a legitimate
current-applicability boundary. The sample therefore stopped before maturity
authority, Futu, Browser, Probability-Free Convexity Discrimination, exact
selection, or any downstream research path.

## Bounded observation and non-claims

Sample 1 locates attrition at Event Intelligence temporal applicability rather
than candidate discovery, human interest, source verification, underlying
mapping, or tooling. It does not show that the lawsuit will be material, that
AMZN volatility will increase, that any option maturity is suitable, or that a
research preference or investment opportunity exists.

```text
campaign_completed_samples = 1 / 5
sample_1_terminal_outcome = EI_NOT_ACCEPTED
```
