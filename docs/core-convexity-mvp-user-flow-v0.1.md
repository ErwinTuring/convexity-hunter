# Core Convexity MVP User Flow v0.1

Status: Approved target; not implemented
Readiness: `CORE_MVP_READY_WITH_APPROVED_ASSUMPTIONS` ([readiness audit](core-convexity-mvp-readiness-v0.1.md))

This compact flow is governed by the
[Core Convexity Research Doctrine](core-convexity-research-doctrine-v0.1.md).
BUILD is authorized against the approved conditional-budget boundary, but this
is still not a frontend, database, or runtime completion claim.

## One Core, three entries

```text
uncertainty / event context
    -> exact supported Long Call / Long Put / same-strike Long Straddle set
    -> geometry
    -> cost / loss budget
    -> sensitivity
    -> survival / repeatability
    -> RESEARCHABLE_CONVEXITY | REJECT | DATA_INSUFFICIENT_CORE
```

- **Direct:** receive one exact supported structure and run the same Core.
- **Discovery:** take all accepted discovery hypotheses, enumerate
  deterministic eligible supported structures within existing maturity
  policies, and run the Core per structure.
- **Event:** take all accepted event hypotheses, use the same deterministic
  enumeration and maturity policies, and run the Core per structure.

There is no target human selection gate in Discovery or Event entry, and no
ATM/Delta inference, ranking, Top-N, score, or “best” choice. The three entry
types differ only in how uncertainty/event context enters; they do not change
Core evidence or disposition semantics.

## User entry examples

- **World:** “Find current eligible supported long-option structures related to
  this world event.” The system grounds the request and runs Event Intelligence
  acceptance; only accepted hypotheses enter deterministic branches. Result: one
  stable case ID, `count_examined`, counts by Core classification, deterministic
  reasons, and compact rows; no pre-generated prose.
- **Event:** “Research whether [event] changes the return distribution of
  [underlying].” The system performs grounding and acceptance first; accepted
  hypotheses continue, while an unaccepted or incomplete branch remains a
  truthful blocked/`DSC_Core` result rather than requiring a pre-supplied
  accepted hypothesis. Result: the same structured summary without ranking.
- **Direct:** “Research this exact supported Long Straddle.” Result: the Core
  disposition and an automatically rendered full report.

## Evidence rules

- Payoff is real only with verified terms, or conditional only with explicit
  standard-payoff approval.
- Indicative asks remain indicative and non-executable; they do not upgrade
  timestamp or authority.
- Fees and other consumed cash flows require an explicit ledger. Missing fees
  are unknown, not zero.
- Portfolio, loss-budget, survival, and repeatability inputs are explicit; no
  defaults or new risk thresholds are introduced.
- Absolute gross hurdles use the existing `M = 1, 2, 5, 10` arithmetic and do
  not require history or a reference price. Relative-to-reference displays do.
- Missing underpricing, history, VolEnv, Tail, percentile, or benchmark
  enhancement evidence does not by itself produce `DATA_INSUFFICIENT_CORE`.

## Presentation and compatibility

Structured records are authoritative. Compact summaries derive from them,
Discovery/Event summaries include stable case ID, examined count, counts by
classification, reasons, and compact rows without pre-generated prose. Lazy
detail reuses the same record and makes no new market-data call except one
permitted by the existing freshness policy. Direct entry automatically renders
the full report. Existing runtime contracts, manual-selection behavior,
screening states, and campaign records remain unchanged versioned evidence
until a later implementation gate.
