# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

## Grounded state

- Branch: `main`
- This checkpoint intentionally stores no static HEAD or parent SHA. A fresh
  thread must run `git fetch origin main`, `git rev-parse HEAD`, and
  `git status --short --branch`; Git is the sole code-state authority.

## Product capability that exists

- The deterministic Convexity Engine, reviewed-artifact candidate assembler,
  screening policy, optional position-management plan, offline
  single-structure service, and Chinese report renderer are implemented.
- Direct Entry separately verifies source-backed exact contract identity and
  complete research readiness. It can process an exact structure when costs,
  liquidity, or other reviewed artifacts are unavailable, while retaining a
  readiness proof only when authentic costs and liquidity both exist.
- The candidate assembler and scanner support truthful partial research and a
  deterministic `DATA_INSUFFICIENT` outcome for omitted downstream artifacts.
- Tiger local credential resolution, exact monthly contract verification,
  transient REST quote evidence, normalized underlying daily history,
  provider-native dividend and historical-option evidence, and exact-contract
  analytics/activity evidence are implemented.
- U.S. Treasury daily par-yield retrieval and the bounded 30–180-day
  par-yield-derived pricing-rate proxy are implemented.
- A narrow OCC/Cboe composite retains Cboe's American/Physical product-level
  terms for eligible Tiger-verified monthly SPY contracts. It remains
  `INCOMPLETE`: unsuffixed `SPY` plus multiplier 100 does not prove the exact
  contract has a standard, unadjusted deliverable, so the existing cost path
  rejects it.

These components now provide a minimal real-market Direct Entry workflow that
honestly terminates at `DATA_INSUFFICIENT`; they do not yet provide complete
research-ready costs or liquidity.

## Highest-priority product gap

The architectural deadlock is removed: a real Tiger-verified exact contract can
be represented by its provider-neutral `OptionContractReference`, enter the
Direct-Entry Reviewed-Research Service with unavailable reviewed artifacts as
`None`, and reach deterministic `DATA_INSUFFICIENT` plus a Chinese report.
There is still no bridge that can produce complete real-provider
`StructureLiquidity` or `StructureCosts` artifacts.

The active product objective is the shortest auditable path:

```text
one caller-specified real Long Call or Long Put
    -> exact Tiger monthly contract verification
    -> provider-neutral exact-contract verification
    -> available reviewed evidence plus explicit missing_data / None artifacts
    -> existing Direct Entry candidate assembly
    -> deterministic screening
    -> Chinese report
```

The durable dependency classification and bounded sequence are in
[`real-direct-entry-vertical-slice-plan.md`](real-direct-entry-vertical-slice-plan.md).

## Active research-readiness gaps

1. Tiger REST option-chain bid/ask has no adequate quote timestamp/session
   semantics and remains transient. It must not become
   `OptionQuoteObservation`.
2. A regular-session Tiger Push BBO probe reached the subscription boundary:
   the exact option subscription was accepted, while the SPY underlying
   subscription was rejected with provider code 4000 (permission denied).
   Explicit quote-permission acquisition did not expose a U.S. stock quote
   entitlement. Because the probe received no qualifying atomic `ALL` frame,
   neither option nor underlying quote normalization is authorized.
3. The Push probe must not be repeated merely because another session opens.
   First establish a U.S. stock Push quote entitlement; then rerun during the
   next valid U.S. regular session after re-confirming market status. The rerun
   must still prove event, bid, ask, exact identity, and session/status binding
   within each atomic frame. No one-time wall-clock date in this checkpoint is
   authoritative.
4. The exact SPY contract's standard/adjusted deliverable status is unresolved.
   OCC explicitly allows rare unsuffixed non-standard options, so absence of a
   numeric suffix or adjustment memo cannot complete the contract reference.
   Cboe's public All Series CSV has no deliverable/adjusted/FLEX field, and its
   Cash-Settled FLEX ETF file lists only eligible underlyings, not exact series.
5. The bounded REST activity/Greeks applicability review is complete and
   authorizes no provider-neutral normalization. Volume lacks a session date
   and completed-session status; open interest lacks its effective session
   date; IV/Greeks lack analytics time, model/rate/dividend descriptions, Vega
   scaling, and Theta day basis. Push quote timestamps cannot fill these REST
   semantic gaps.

Push BBO is a bounded parallel blocker, not permission to weaken semantics or
to resume unrelated market-data infrastructure.

## Real partial-loop validation

On 2026-08-11, one repository-external sanitized live check used the user's
external Tiger configuration and retained no raw payload. It confirmed:

- authentication and exact provider-monthly contract verification succeeded;
- the provider-neutral contract reference remained `INCOMPLETE`;
- exact-contract verification succeeded without research-readiness proof;
- zero reviewed numerical artifacts entered Candidate Assembly;
- both candidate and screening states were `DATA_INSUFFICIENT`;
- no position-management plan was created; and
- a nonempty `zh-CN` report was rendered.

No account identifier, contract identifier, raw market payload, credential,
or secret was persisted or added to the repository.

## Regular-session Push BBO validation

On 2026-08-11, a repository-external sanitized probe first confirmed both the
U.S. regular-session clock window and Tiger's `TRADING` market status. The
exact-option subscription acknowledgement succeeded. The SPY underlying
subscription acknowledgement returned code 4000, which Tiger documents as
permission denied. An explicit local quote-permission acquisition succeeded
but exposed no U.S. stock quote entitlement, and an immediate retry produced
the same result.

The probe stopped at the subscription boundary with no qualifying atomic
`ALL` event and shut down cleanly. It persisted no raw frame, symbol,
credential, account identifier, or market payload. Consequently:

- `OptionQuoteObservation` normalization remains unauthorized;
- `UnderlyingQuoteObservation` normalization remains unauthorized;
- quote scope remains unset (not even `PROVIDER_COMPOSITE` is authorized);
- option open-interest and Greeks normalization remain paused; and
- the remaining external blocker is U.S. stock Push quote entitlement before
  another next-valid-regular-session probe can be informative.

## Next work

1. Establish U.S. stock Push quote entitlement, then during the next valid
   U.S. regular session complete the bounded atomic Option/underlying Push BBO
   probe.
2. If authoritative quote semantics are proven, freeze only the smallest
   option/underlying quote normalization boundary; activity/Greeks remain
   unavailable unless separate authoritative semantics emerge.
3. Keep the cost and liquidity paths closed until each existing input authority
   is satisfied; do not infer deliverable, activity, or Greek semantics.
4. Reuse existing Direct Entry, assembly, screening, and report authorities
   without duplicating numerical or policy logic.

## Explicitly deferred

- additional Treasury/rate sophistication;
- forward-dividend, historical-IV, and volatility-surface platforms unless a
  demonstrated vertical-slice blocker requires a bounded unit;
- broad scanning, structure generation, Event Intelligence, and
  event-to-underlying mapping until one real Direct Entry slice works;
- provider routing/arbitration, portfolio optimization, monitoring, alerts,
  recommendations, execution, and heavy orchestration/governance frameworks.

Historical work-unit details remain in contracts, Git history, and the
historical ledger in `project-state.md`; they do not determine current
priority.
