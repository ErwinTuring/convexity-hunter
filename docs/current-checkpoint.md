# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Contract base:

- branch: `main`
- commit: `74f2698`
- subject: `Define direct-entry reviewed research service contract`

Finalized work-unit subject:

`Implement direct-entry reviewed research service`

The Deterministic Direct-Entry Reviewed-Research Service is implemented and
independently reviewed. Its direct module and focused tests are:

- `src/convexity_hunter/direct_entry_reviewed_research_service.py`
- `tests/test_direct_entry_reviewed_research_service.py`

Canonical contract:

- [`docs/direct-entry-reviewed-research-service-contract.md`](direct-entry-reviewed-research-service-contract.md)

The service composes exact-structure verification, the existing 21-argument
candidate assembler, and the existing offline screening/plan/Chinese-report
service. It preserves delegated object identities and error order without
adding local eligibility, numerical, lineage, or policy authority.

Independent review returned `IMPLEMENTATION REVIEW RESULT: PASS`. Final
validation passed 11 focused tests, 1,059 full-suite tests, compilation, and
`git diff --check`. The package root and all existing producer APIs remain
unchanged. Provider access, chain retrieval, incomplete-description resolution,
eligibility policy, generation, monitoring, and execution remain absent.

Completed Tiger local runtime work unit:

- Tiger OpenAPI is selected as the MVP primary market-data provider.
- Canonical contract: [`tiger-provider-contract.md`](tiger-provider-contract.md).
- Contract base: `2da29f2` (`Define Tiger local runtime boundary`).
- Finalized work-unit subject: `Implement Tiger local runtime boundary`.
- The implementation adds exact path-only local configuration discovery and
  non-networking, non-preempting SDK client initialization.
- No credential content, market-data retrieval, provider normalization, or
  downstream service modification is in scope.
- Independent review findings were corrected and targeted re-review passed.
  Final validation passed 26 focused tests, 1,085 full-suite tests, compileall,
  `git diff --check`, and a sanitized local external-config smoke check.

Completed Tiger exact option-contract verification work unit:

- Canonical contract:
  [`tiger-option-contract-verification-contract.md`](tiger-option-contract-verification-contract.md).
- Contract base: `81aae8c` (`Define Tiger exact contract verification`).
- Finalized work-unit subject: `Implement Tiger exact contract verification`.
- The direct Tiger module verifies one caller-specified underlying, expiration,
  call/put, and strike against Tiger's explicit `period_tag=m` expiration row
  and exactly one exact chain row.
- The frozen result retains Tiger's identifier, expiration timestamp, and
  provider-supplied multiplier with a provider-neutral
  `OptionContractReference` and two timestamped source references.
- It performs no discovery ranking, nearest-contract substitution, quote or
  analytics normalization, permission grab, credential handling, or trading.
- Four accepted independent-review findings were corrected; final targeted
  re-review passed. Final validation passed 39 focused tests, 1,098 full-suite
  tests, compileall, `git diff --check`, and a sanitized live SPY monthly
  exact-contract smoke check.

Completed Tiger exact option-quote evidence work unit:

- Canonical contract:
  [`tiger-exact-option-quote-evidence-contract.md`](tiger-exact-option-quote-evidence-contract.md).
- Contract base: `69143b4` (`Define Tiger exact option quote evidence`).
- Finalized work-unit subject: `Implement Tiger exact option quote evidence`.
- The direct Tiger module proves active `usOptionQuote` entitlement and returns
  frozen bid/ask/size evidence for one already verified exact contract.
- Permission and quote receipt times are captured by the adapter; positive
  permission expiry must remain active through quote receipt.
- Because Tiger supplies no quote timestamp or quote session date, the unit
  intentionally creates no `OptionQuoteObservation`, session date, market
  phase, quote scope, freshness claim, or delayed-status claim.
- Four accepted independent-review findings were corrected; targeted
  re-review passed. Final validation passed 51 focused tests, 1,110 full-suite
  tests, compileall, `git diff --check`, and a sanitized live SPY exact-contract
  permission/bid/ask evidence smoke check.
- Follow-up decision: REST quote evidence remains transient. The next
  feasibility unit validates Tiger option Push BBO timestamps, event time, and
  session binding. If reliable, Push BBO becomes the canonical current-quote
  source with conservative `PROVIDER_COMPOSITE` scope; REST remains the source
  for contract reference, activity, and provider analytics.
- SDK 3.7.0 inspection confirms the raw Push event has the required candidate
  fields, split by Python into Basic and BBO callbacks sharing event timestamp.
  A non-trading-day live probe authenticated and acknowledged the subscription
  without errors but produced no quote event, so regular-session field
  population and pairing remain the next required live check.

Completed Tiger underlying daily-bars work unit:

- Canonical contract:
  [`tiger-underlying-daily-bars-contract.md`](tiger-underlying-daily-bars-contract.md).
- Contract base: `e7b23ef` (`Define Tiger underlying daily bars`).
- Finalized work-unit subject: `Implement Tiger underlying daily bars`.
- The direct Tiger module pairs exact unadjusted `NR` daily OHLC/volume with
  `BR` forward-adjusted close for a bounded completed-session range and returns
  the existing provider-neutral `UnderlyingDailyBarObservation`.
- Two accepted failure-precedence findings were corrected so invalid, empty,
  or core-inconsistent NR material fails before the BR request; final targeted
  re-review passed.
- Final validation passed 60 focused tests, 1,119 full-suite tests, compileall,
  `git diff --check`, and a sanitized live five-session SPY smoke check.

Frozen next Tiger work unit:

- Canonical contract:
  [`tiger-historical-dividend-evidence-contract.md`](tiger-historical-dividend-evidence-contract.md).
- Direct `DividendObservation` normalization is blocked because Tiger does not
  authoritatively specify per-share amount units or regular/special type.
- The bounded unit retains complete provider-native historical evidence only;
  implementation and independent review are pending.

This file is a concise navigation map, not a complete specification or
history.
