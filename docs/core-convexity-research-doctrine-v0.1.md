# Core Convexity Research Doctrine v0.1

Status: Accepted
Decision date: 2026-09-18
Readiness: `CORE_MVP_BLOCKED` ([readiness audit](core-convexity-mvp-readiness-v0.1.md))

## Context

The repository contains useful but differently scoped evidence: exact-payoff
geometry, optional volatility/tail/history transforms, legacy screening states,
and a runtime browser with explicit human selection. Without an explicit target
boundary, those facts can be read as one unqualified product requirement.

The authoritative research input for this correction is
`/Users/erwinlee/convexity-hunter/research/taleb-preflight-2026-09-17/TALEB_MINIMAL_MODEL_PREFLIGHT.md`.
It supports a minimal, probability-free core and does not claim that the model
or its market-data gaps are ready.

This ADR is a product-target decision approved independently of implementation
readiness. It changes no production code, tests, provider contract, database,
frontend, or historical campaign record.

## Decision

### Scope and non-negotiable distinctions

The target Core researches one exact supported long structure at a time:
Long Call, Long Put, or a same-strike, same-expiration Long Straddle, within
the existing maturity policies. It is a deterministic research disposition,
not a directional prediction or investment decision.

Positive convexity, underpricing, and recommendation are separate predicates:

- **Convexity** is exact payoff geometry under verified terms or an explicitly
  approved conditional standard-payoff assumption.
- **Underpricing** requires a lawful, explicit benchmark and is optional
  enhancement evidence; geometry alone does not establish it.
- **Recommendation** is outside the product scope. No Core result is a buy,
  sell, expected-return, probability, or execution instruction.

Missing underpricing evidence or long option history does not invalidate the
Core. Volatility-environment, tail, percentile, benchmark, and similar
enhancements remain claim-triggered and optional. Existing code and versioned
contracts are preserved.

### Target flow and three equivalent entries

All three entries converge on the same structured Core record and the same
disposition path:

```text
uncertainty / event context
    -> exact supported structures
    -> payoff geometry
    -> explicit cost / loss budget
    -> sensitivity
    -> survival / repeatability
    -> deterministic Core disposition
```

1. **Direct entry** receives an exact supported structure and runs the Core.
2. **Discovery entry** processes all accepted discovery hypotheses and
   deterministically enumerates eligible Long Calls, Long Puts, and
   same-strike Long Straddles within the existing maturity policies.
3. **Event entry** processes all accepted event hypotheses through the same
   deterministic structure enumeration and Core.

Discovery and Event entry have no human selection gate in the approved target.
They do not infer ATM or Delta, rank, score, choose Top-N, or select a “best”
structure. Deterministic eligibility is not a recommendation. A later
implementation contract must define how existing runtime boundaries bridge to
this target; this ADR does not implement that bridge.

### Core inputs and fail-closed semantics

The Core requires explicit, non-defaulted inputs needed by the selected claim:

- exact identity, supported structure grammar, maturity, quantity, and
  multiplier;
- real payoff/exercise/settlement terms, **or** an explicit conditional
  standard-payoff approval. Neither may be inferred from a provider label;
- valid positive ask-basis inputs for the selected legs. Indicative asks remain
  `INDICATIVE_ONLY`; they never become executable prices or a timestamp/authority
  upgrade;
- an explicit fee/funding/settlement/assignment/slippage ledger wherever the
  cost or loss claim consumes those items. Missing entries are `unknown`, never
  zero;
- explicit portfolio and survival/repeatability inputs, including the caller's
  applicable loss-budget methodology. No portfolio value, boundary, count, or
  threshold is defaulted or invented.

Absolute gross expiration hurdles do not require a history or reference price.
Using the existing gross-value multiples only (`M` in `{1, 2, 5, 10}`), the
existing arithmetic is `K + M*A` for a call, `K - M*A` for a put, and the two
levels for a same-strike straddle. `A` is the stated per-underlying-unit ask
basis. A `1x` gross payout is not net profit, formal break-even, expected
return, or probability. A ratio or move relative to `R` requires an explicit,
lawful reference and is not needed for the absolute hurdle.

`DATA_INSUFFICIENT_CORE` is reserved for missing mandatory Core inputs. It is
not a catch-all for absent optional history, VolEnv, Tail, percentile, or
benchmark evidence. A deterministic hard contradiction or disqualifying
structure may produce `REJECT`; missing required evidence produces
`DATA_INSUFFICIENT_CORE`.

The target dispositions are exactly:

- `RESEARCHABLE_CONVEXITY`: mandatory Core evidence is complete, the exact
  structure is within the supported model, and the explicit survival/
  repeatability policy is satisfied. This is a Core disposition, not merely a
  statement that the structure is “researchable”; it does not assert
  underpricing or a trade;
- `REJECT`: a deterministic Core exclusion or hard failure is established;
- `DATA_INSUFFICIENT_CORE`: a mandatory Core input is absent or unresolved.

These dispositions do not replace or reinterpret legacy `ScreeningDecision`,
`DATA_INSUFFICIENT`, `WATCH`, or `INVESTIGATE` values in existing contracts.

### Records and presentation

Each stage produces structured records. Compact summaries are derived from
those records. Discovery/Event default output includes a stable case ID,
`count_examined`, counts by classification, deterministic reasons, and compact
rows; it does not pre-generate prose. Lazy detail reuses the same record and
lineage rather than recomputing or choosing a new source, and makes no new
market-data call except one expressly permitted by the existing freshness
policy. Direct entry automatically renders the full report. This target
decision adds no database or frontend requirement.

### Runtime and readiness boundary

The current runtime, legacy manual-selection contracts, old screening
contracts, and historical campaign records remain versioned evidence and stay
unchanged. This doctrine supersedes their unqualified product-target wording
only; it does not claim that the target flow is built. The current task is
authorized to proceed to BUILD once the specific loss/survival method boundary
is resolved; this does not imply a new product approval for every
implementation. Readiness remains `CORE_MVP_BLOCKED`; see the
[readiness audit](core-convexity-mvp-readiness-v0.1.md).

## Rationale

The separation keeps exact convex payoff geometry useful when a lawful
underpricing benchmark or long history is unavailable, while preventing
geometry from being mislabeled as cheapness or advice. Explicit cost and
survival inputs keep unknown cash flows and portfolio assumptions from being
silently replaced with zeros or defaults. A common Core prevents entry mode
from changing the research standard.

## Rejected alternatives

- Requiring long option history, VolEnv, Tail, percentile, or a benchmark
  before any Core result.
- Calling a convex structure “underpriced” from payoff geometry alone.
- Ranking, Top-N selection, ATM/Delta inference, or a “best” structure.
- Treating missing fees, funding, or portfolio inputs as zero/default values.
- Upgrading indicative asks into executable evidence or declaring the target
  ready from this documentation change.

## Related documents

- [Core Convexity MVP user flow](core-convexity-mvp-user-flow-v0.1.md)
- [Project Philosophy](philosophy.md)
- [MVP Specification](mvp-spec.md)
- [Product Direction](product-direction.md)
- [Project State](project-state.md)
- [Current Checkpoint](current-checkpoint.md)
