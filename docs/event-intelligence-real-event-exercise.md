# Event Intelligence Real-Event Exercise

## Scope

On 2026-08-19, the implemented acceptance boundary was exercised outside the
repository with one historical, filing-driven real event. The exercise tested
typed acceptance only. It did not retrieve market data, generate option
structures, persist a provider payload, invoke an LLM, or install a Skill.

## Authoritative source

The sole source was the SEC filing index for Apple Inc. Form 8-K accession
`0000320193-25-000071`, filed and accepted on 2025-07-31:

<https://www.sec.gov/Archives/edgar/data/320193/000032019325000071/0000320193-25-000071-index.htm>

The filing identifies Apple common stock as `AAPL` on The Nasdaq Stock Market
LLC and reports that Apple issued third-fiscal-quarter results on that date.
Those statements were retained as observed facts. The possible short-horizon
bidirectional distribution expansion was retained separately as an
interpretation and hypothesis, not as a filing fact.

## Sanitized result

```text
assessment version: event-intelligence-acceptance-v0.1
status: ACCEPTED
issue codes: none
sources: 1
observed facts: 2
interpretations: 1
hypotheses: 1
underlying: AAPL / XNAS / equity / USD
event date: 2025-07-31
declared expected window: 2025-07-31 through 2025-08-07 inclusive
market data consumed: NO
raw external payload persisted: NO
```

The expected window was explicitly labeled an MVP exercise assumption rather
than an issuer or provider forecast. The submission also disclosed that the
single filing cannot establish whether results were already priced, that no
market reaction was consumed, and that the contradiction review was not
exhaustive.

## Adapter decision

Do not add an SEC adapter yet. One deterministic metadata adapter could map
filing identity, dates, issuer, ticker, exchange text, and source locator, but
it could not authoritatively supply the impact path, distribution hypothesis,
contradiction review, uncertainties, or falsification conditions. The real
exercise succeeded without repository integration, so a new adapter would not
remove the current product blocker and is not yet justified by repeated use.

The next bounded work is the discovery-entry handoff from one accepted
Event Intelligence result. It must consume the accepted proof without replaying
or weakening acceptance and must remain separate from option-chain retrieval
and exact structure generation until those later contracts are frozen.
