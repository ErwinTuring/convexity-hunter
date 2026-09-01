# Hunter End-to-End Validation — Sample 2

Date: 2026-09-02

## Scope

This sanitized product record is Sample 2 of the five-sample campaign frozen
in the
[`Hunter End-to-End Validation Protocol v0.1`](hunter-end-to-end-validation-protocol.md).
It changed no production code, schema, policy, acceptance rule, maturity
authority, provider boundary, or discrimination metric.

## Discovery batch and human checkpoint

The bounded public Web Search producer applied
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) to the exact
inclusive source-publication window:

```text
window_start = 2026-07-21
window_end = 2026-07-27
observed_at = 2026-09-01T23:23:09Z
candidate_count = 7
```

The window was the most recent complete unused seven-calendar-day window
immediately before the already-used continuous 2026-07-28 through 2026-09-02
sequence. The exact production `EventCandidateBatch` validator passed with
neutral earliest-publication/candidate-ID order, no padding, no option-market
feedback, six `EXPLICIT_CATALYST` records, one
`NARRATIVE_BELIEF_SHIFT` record, and no manufactured
`SECOND_ORDER_TRANSMISSION` record.

The human explicitly selected:

```text
candidate_id = 2026-07-22-explicit-apxt-tecfusions-business-combination
selected_discovery_lane = EXPLICIT_CATALYST
willingness_to_continue = yes
event_new_to_human = yes
connection_new_to_human = yes
impact_transmission_credibility = mixed
```

The human rejected the other candidates principally because they were
post-approval commercialization cases with possibly limited parent-company
importance, or conventional transaction and take-private events with clear but
lower-incremental-value outcome paths. APXT/TECfusions remained worth reviewing
because SPAC redemption and financing risk, the USD 4 billion transaction
valuation, power-secured data-center claims, and post-combination delivery
created several still-open paths that transmit directly to APXT. Credibility
remained mixed because capacity, power, customer-demand, and economic claims
were not yet sufficiently verified.

## Supplemental verification and translation

Translation retained the selected candidate's SEC-filed announcement and added
only the filed [Apex Treasury Form 8-K](https://www.sec.gov/Archives/edgar/data/2079253/000121390026080199/ea0298664-8k425_apex.htm)
and executed
[Business Combination Agreement](https://www.sec.gov/Archives/edgar/data/2079253/000121390026080199/ea029866401ex2-1.htm).
The exact event range became the 2026-07-21 agreement date through the
2026-07-22 Form 8-K and public announcement date. The resolved underlying was
`APXT / XNAS / EQUITY / USD`.

The fact-versus-interpretation graph retained:

- the signed agreement, USD 4.0 billion pre-money valuation, approximately
  USD 4.2 billion pro-forma enterprise value under a no-redemption assumption,
  and USD 35 million gross committed PIPE;
- issuer-reported live, contracted, and potential site-capacity claims as
  issuer representations rather than independently verified operations;
- shareholder approval, redemption, financing, closing, termination, and
  post-combination delivery paths;
- the agreement's exact 2026-09-30 deadline for specified PCAOB and
  first-quarter financial statements, including Apex Treasury's related
  termination right; and
- the 2027-03-31 Outside Date and its stated termination conditions.

No complete expected market-impact window was supported. Translation therefore
preserved:

```text
expected_window = absent
```

The 2026-09-30 financial-statement deadline supplied one exact source-backed
future observable milestone that was directly relevant to reviewing transaction
economics and execution evidence. The caller constructed:

```text
reassessment_by = 2026-09-30
basis_kind = SOURCE_BACKED_MILESTONE
methodology = source-backed-milestone:fact-pcaob-financials-milestone:2026-09-30
```

This is a research-governance boundary only. It is not an expected impact end,
expected closing date, narrative-duration estimate, holding period, or option-
maturity anchor.

## Event Intelligence and option-research result

The production Event Intelligence v0.2 acceptance boundary returned:

```text
status = ACCEPTED
issue_codes = ()
```

With evaluation date 2026-09-01, the currently applicable structural-only
hypothesis entered the explicit neutral path:

```text
maturity_authority = NEUTRAL_STRUCTURAL_RESEARCH
hypothesis_maturity_alignment = NOT_ESTABLISHED
minimum_expiration = 2026-10-01
maximum_expiration = 2027-01-29
```

The local authenticated Futu OpenD request completed successfully for
`US.APXT`. It returned:

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

Sample 2 confirms that the existing product can preserve a newly selected
mixed-credibility SPAC/infrastructure hypothesis through source-backed
translation and Event Intelligence acceptance without inventing an impact end.
It then locates attrition at the absence of a real listed APXT option surface.

The result does not show that the transaction will close, that the disclosed
capacity is economically durable, that APXT is attractive, or that another
underlying should be substituted. It also does not test whether the
Probability-Free Convexity Discrimination surface would produce a human
preference, because no legitimate option comparison surface existed.

```text
campaign_completed_samples = 2 / 5
sample_2_terminal_outcome = NO_OPTION_RESEARCH_SURFACE
```
