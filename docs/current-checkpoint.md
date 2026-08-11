# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

## Grounded state

- Branch: `main`
- Grounded parent baseline for this checkpoint:
  `263a712699b3b993defb294217d64371016211bc`
  (`Add authoritative SPY option terms composite`). The current correction is
  committed after that parent; `git rev-parse HEAD` remains the authoritative
  current SHA.
- A fresh thread must still run `git fetch origin main`, `git rev-parse HEAD`,
  and `git status --short --branch`; this file does not replace Git.

## Product capability that exists

- The deterministic Convexity Engine, reviewed-artifact candidate assembler,
  screening policy, optional position-management plan, offline
  single-structure service, and Chinese report renderer are implemented.
- Direct Entry can verify and process one already-reviewed exact structure
  when authentic `StructureCostsTransformationResult` and
  `StructureLiquidityTransformationResult` artifacts already exist.
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

These are components, not yet a usable real-market Direct Entry workflow.

## Highest-priority product gap

There is no implemented bridge from one real Tiger-verified exact structure to
the provider-neutral current records and relationship proofs consumed by
`transform_structure_liquidity` and `transform_structure_costs`. Consequently
the current Direct-Entry Reviewed-Research Service still requires artifacts
that no real-provider orchestration path produces.

The active product objective is the shortest auditable path:

```text
one caller-specified real Long Call or Long Put
    -> exact Tiger monthly contract verification
    -> authoritative current snapshot records and proofs
    -> existing liquidity and cost transformations
    -> existing Direct Entry verification and candidate assembly
    -> deterministic screening
    -> Chinese report
```

The durable dependency classification and bounded sequence are in
[`real-direct-entry-vertical-slice-plan.md`](real-direct-entry-vertical-slice-plan.md).

## Active blockers

1. Tiger REST option-chain bid/ask has no adequate quote timestamp/session
   semantics and remains transient. It must not become
   `OptionQuoteObservation`.
2. The scheduled regular-session Tiger Option Push BBO probe must prove event,
   bid, ask, exact-contract, and session/status binding before normalization.
   Run it only during the next valid U.S. regular session and re-confirm market
   status at execution; no one-time wall-clock date in this checkpoint is
   authoritative.
3. The same vertical slice also needs an authoritative current underlying
   bid/ask path with timestamp/session semantics; no such Tiger adapter exists.
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

## Next work

1. During a valid U.S. regular session, complete the bounded Option Push BBO
   probe and separately establish the viable Tiger current-underlying quote
   path.
2. If authoritative quote semantics are proven, freeze only the smallest
   option/underlying quote normalization boundary; activity/Greeks remain
   unavailable unless separate authoritative semantics emerge.
3. Keep the cost path closed until an authoritative exact-contract deliverable
   source is available; do not infer standard status from OSI root syntax.
4. Build no thin liquidity/cost bridge until quote, exact-deliverable,
   activity, and Greeks inputs all satisfy their existing authorities.
5. Reuse existing Direct Entry, assembly, screening, and report authorities
   without duplicating numerical or policy logic.
6. Permit honest `DATA_INSUFFICIENT` for volatility environment, tail pricing,
   scenarios, expiration thresholds, and affordability until a concrete
   vertical-slice need justifies their missing real producers.

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
