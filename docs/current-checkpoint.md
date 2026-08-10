# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

## Grounded state

- Branch: `main`
- Grounded parent baseline for this checkpoint:
  `f1e4c3a5dd9e844371f606e60554742d1c959ff5`
  (`Recenter roadmap on real Direct Entry`). This checkpoint and the bounded
  SPY standard-option terms composite are committed together after that base;
  `git rev-parse HEAD` remains the authoritative current SHA.
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
- Exact Tiger-verified standard monthly SPY contracts can be completed with
  authoritative American/Physical terms by the narrow OCC/Cboe system
  composite; adjusted/numeric-root and non-SPY contracts fail closed.

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
   Its next executable window is **2026-08-10 21:30 Asia/Shanghai**
   (2026-08-10 09:30 America/New_York); a fresh thread must not repeat the
   probe before that regular-session window.
3. The same vertical slice also needs an authoritative current underlying
   bid/ask path with timestamp/session semantics; no such Tiger adapter exists.
4. Tiger REST analytics/activity evidence does not authoritatively supply an
   analytics observation time/session, model/rate/dividend descriptions, or
   Theta day basis. It cannot yet be promoted to provider-neutral IV/Greeks
   records by inference.

Push BBO is a bounded parallel blocker, not permission to weaken semantics or
to resume unrelated market-data infrastructure.

## Next work

1. During a valid U.S. regular session, complete the bounded Option Push BBO
   probe and separately establish the viable Tiger current-underlying quote
   path.
2. If authoritative semantics are proven, freeze the smallest one-leg Tiger
   current-snapshot normalization/relationship bridge.
3. Reuse existing liquidity, cost, Direct Entry, assembly, screening, and
   report authorities without duplicating numerical or policy logic.
4. Permit honest `DATA_INSUFFICIENT` for volatility environment, tail pricing,
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
