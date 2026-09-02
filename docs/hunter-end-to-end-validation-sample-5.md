# Hunter End-to-End Validation — Sample 5

Date: 2026-09-03

## Scope

This sanitized product record is Sample 5 of the five-sample campaign frozen
in the
[`Hunter End-to-End Validation Protocol v0.1`](hunter-end-to-end-validation-protocol.md).
It changed no production code, schema, policy, acceptance rule, maturity
authority, provider boundary, or discrimination metric.

## Discovery batch and human checkpoint

The bounded public Web Search producer applied
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) to the exact
inclusive source-publication window:

```text
window_start = 2026-06-30
window_end = 2026-07-06
observed_at = 2026-09-02T16:23:36Z
candidate_count = 9
```

In the campaign's reverse-chronological sequence, this was the most recent
complete unused seven-calendar-day window immediately preceding Sample 4's
2026-07-07 through 2026-07-13 window. The exact production
`EventCandidateBatch` validator passed with neutral earliest-publication/
candidate-ID order, no padding, no option-market feedback, nine
`EXPLICIT_CATALYST` records, and no manufactured records in the other two
lanes.

The human explicitly selected:

```text
candidate_id = 2026-07-06-explicit-ipw-convertible-facility-draw
selected_discovery_lane = EXPLICIT_CATALYST
willingness_to_continue = yes
event_new_to_human = yes
connection_new_to_human = yes
impact_transmission_credibility = credible
```

The human rejected the other candidates principally because they concerned
large-company regulatory or compliance matters whose enterprise-level
importance remained unclear, completed transactions or approvals with limited
residual dispersion, or early clinical evidence that remained primarily a
development update. IPW remained worth reviewing because cash proceeds,
original-issue discount, secured claims, future draw capacity, payment terms,
and conversion-linked dilution act directly on a financing-dependent
company's survival path. Financing sufficiency relative to cash consumption,
future draw conditions, conversion mechanics, and use of proceeds remained
unestablished.

## Supplemental verification and translation

Translation retained the selected candidate's
[SEC-filed Form 8-K](https://www.sec.gov/Archives/edgar/data/1830072/000168316826005288/ipower_8k.htm)
and added only three authoritative public filings:

- iPower's
  [Series A resale registration statement](https://www.sec.gov/Archives/edgar/data/1830072/000168316826005462/ipower_s1.htm);
- iPower's
  [Form 10-Q for the quarter ended 2026-03-31](https://www.sec.gov/Archives/edgar/data/1830072/000168316826004180/ipower_i10q-033126.htm); and
- iPower's
  [AI-subsidiary guaranty Form 8-K](https://www.sec.gov/Archives/edgar/data/1830072/000168316826005670/ipower_8k.htm).

The exact event date was 2026-07-06. The resolved underlying was
`IPW / XNAS / EQUITY / USD`. The eleven-statement fact-versus-interpretation
graph retained:

- the amended senior-secured convertible facility, USD 2 million principal
  closing, USD 1.88 million gross proceeds before fees and expenses, fixed
  conversion price, and remaining facility capacity;
- senior-secured status, interest and payment mechanics, conversion-share
  path, and the first-payment commencement date for the latest note;
- reported March cash, losses, existing funding sources, and management's
  conditional liquidity statement;
- the later guaranty joinder by iPower AI LLC; and
- the provisional transmission from draw availability, secured obligations,
  payment form, conversion, default terms, cash use, and future funding to
  IPW's liquidity runway, dilution, creditor control, and operating execution.

No complete expected market-impact window was supported:

```text
expected_window = absent
```

The registration statement supplied an exact future observable milestone: the
latest note's first payment commences on 2026-10-01. The caller constructed:

```text
reassessment_by = 2026-10-01
basis_kind = SOURCE_BACKED_MILESTONE
methodology = source-backed-milestone:fact-note-payment-milestone:2026-10-01
```

This is only a research-governance boundary for checking payment form,
outstanding principal, conversion or redemption activity, and whether the
financing-path hypothesis remains current. It is not an expected impact end,
default forecast, holding period, or option-maturity anchor.

## Event Intelligence and option-research result

The production Event Intelligence v0.2 acceptance boundary returned:

```text
status = ACCEPTED
issue_codes = ()
```

At the 2026-09-03 evaluation date, the currently applicable structural-only
hypothesis entered the explicit neutral path:

```text
maturity_authority = NEUTRAL_STRUCTURAL_RESEARCH
hypothesis_maturity_alignment = NOT_ESTABLISHED
minimum_expiration = 2026-10-03
maximum_expiration = 2027-01-31
```

The local authenticated Futu OpenD request completed successfully for
`US.IPW`. It returned:

```text
provider_expirations = 0
all_chain_contracts = 0
browser_visible_rows = 0
same_strike_call_put_pairs = 0
terminal_outcome = NO_OPTION_RESEARCH_SURFACE
```

This is a product result, not a provider or tooling failure. The experiment did
not substitute another underlying, widen the maturity interval, rerun for a
different answer, manufacture a structure, retrieve quotes, or invoke
Probability-Free Convexity Discrimination.

## Bounded observation and non-claims

Sample 5 confirms that a newly selected financing-survival hypothesis can pass
source-backed translation and Event Intelligence acceptance without inventing
an impact end. It then locates attrition at the absence of a real listed IPW
option surface, as Sample 2 did for APXT.

The result does not establish that iPower has adequate or inadequate runway,
that conversion or default will occur, that the financing is attractive or
harmful, or that another underlying should be substituted. It also does not
test whether Probability-Free Convexity Discrimination would produce a human
preference because no legitimate option comparison surface existed.

```text
campaign_completed_samples = 5 / 5
sample_5_terminal_outcome = NO_OPTION_RESEARCH_SURFACE
```
