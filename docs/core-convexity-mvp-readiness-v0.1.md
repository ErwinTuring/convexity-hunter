# Core Convexity MVP Readiness v0.1

Status: `CORE_MVP_READY_WITH_APPROVED_ASSUMPTIONS`
Decision: final Main readiness decision; implementation progress below
Decision date: 2026-09-18

This audit distinguishes method/input readiness from implementation. `READY`
means a method or reusable input boundary is available; it does not mean the
target runtime is implemented. The runtime/build column is explicit.

Pre-documentation baseline: fetched clean at HEAD
`7bd0cf1739b259ab247df47c9894486c802f59a9`; that audit was documentation-only.
Evidence environment: Futu API `10.10.7008` with OpenD `11111` listening; this
does not establish authentication, quote authority, or executable data.

Source anchors use full paths under `src/convexity_hunter/`: `event_discovery.py`,
`event_entry_preparation.py:219`, `research_case.py`,
`providers/futu.py:483,1356,2570`, `risk_assessment.py`,
`convexity_discrimination.py:769-859`, `convexity_presentation.py:60-61`,
and `report.py:1973`.

`READY_WITH_EXPLICIT_APPROVED_ASSUMPTION` applies only to the now-approved
conditional budget boundary; it never means actual safety or executability.

## Implementation progress — 2026-09-19

The Core kernel and three-entry application implementation passed independent
review and targeted re-review. Twenty kernel and ten application tests pass.
The user-flow document records final validation and the real Direct smoke
case. World/Event source callables remain operational prerequisites; their
absence is not presented as live three-entry completion.
The following matrix is the original pre-BUILD readiness snapshot, not a live
inventory of implementation files. Missing caller risk/cost policy remains a
case-level `DATA_INSUFFICIENT_CORE` outcome, not permission to invent defaults.

## 20-item pre-BUILD audit

| # | Item and evidence | Status | Method/input | Runtime/build state |
|---:|---|---|---|---|
| 1 | Supported Long Call/Put/same-strike Straddle model, exact identity, quantity, and multiplier | READY | Scope and exact inputs reusable | Target runtime not implemented |
| 2 | World/discovery intake and Event Intelligence acceptance: `src/convexity_hunter/event_discovery.py:148,248,319,412` | READY | Bounded records, provenance, and accepted-result input | Current human-choice boundary; all-hypothesis target is build gap |
| 3 | Event Entry preparation: `src/convexity_hunter/event_entry_preparation.py:219` | READY | Identity-preserving input binding | Current explicit hypothesis selection; target no-gate bridge absent |
| 4 | ResearchCase: `src/convexity_hunter/research_case.py:213,707-708,873-875,1041` | READY | In-memory retained sidecars | Current manual/offline composition only |
| 5 | Direct exact-structure entry: existing direct-entry contracts | READY | Exact structure input is reusable | No target automatic full-flow claim |
| 6 | Futu exact verification: `src/convexity_hunter/providers/futu.py:483` | READY | Exact contract verification method | Auth/quote authority not established |
| 7 | Futu Browser: `src/convexity_hunter/providers/futu.py:1356-1359` | READY | Neutral eligible-row input | Existing manual browser; target enumeration not built |
| 8 | Futu quote batch: `src/convexity_hunter/providers/futu.py:2570-2576` | READY | Indicative ask input is reusable | Indicative only; no executable or timestamp upgrade |
| 9 | Existing maturity policies | READY | Reuses current policy | No new maturity policy implemented |
| 10 | Conditional geometry: `src/convexity_hunter/convexity_discrimination.py:769-859` | READY_WITH_EXPLICIT_APPROVED_ASSUMPTION | Conditional payoff math reusable | Not real payout or Core qualification |
| 11 | Existing gross hurdles, no-history absolute arithmetic, and caller-declared sensitivity | READY | Existing math and descriptive scenarios reusable | Current path still carries reference/runtime constraints |
| 12 | Exact costs → current RiskAssessment/`StructureCosts`: `src/convexity_hunter/risk_assessment.py:1138-1171,1329-1416` | READY | Exact dependency is reusable | Raw `A` cannot fabricate its dependencies |
| 13 | Fee/funding/settlement ledger and complete caller cost upper bound | READY | Explicit ledger rule is reusable | Missing entries yield runtime `DSC_Core`, never zero |
| 14 | Portfolio/loss-budget/repeat-loss policy inputs | READY | Caller inputs and no-default boundary | Missing required inputs yield `DSC_Core`; no hidden count or ratio |
| 15 | Loss/survival qualification under approved conditional boundary | READY_WITH_EXPLICIT_APPROVED_ASSUMPTION | Conditional budget may qualify Core only with all stated inputs | Runtime/build pending; never actual safety, survival proof, or executability |
| 16 | Premium-only prohibition and conservative `DSC_Core` branch | READY | No premium-only pass; missing mandatory input is DSC | Missing policy instance is runtime DSC, not a build blocker |
| 17 | All accepted hypotheses; no human gate/ATM-Delta/rank/Top-N/best | BLOCKED | Target method direction is frozen | Current selection path remains; missing target module is a build gap, not a second approval blocker |
| 18 | Default batch records: stable case ID, examined count, classification counts, reasons, compact rows, no prose; lazy detail | BLOCKED | Required output contract is explicit | New module/build item; no new market call except freshness policy |
| 19 | Renderers/full reports: `convexity_presentation.py:60-61`, `report.py:1973`, `research_case.py:1230` | BLOCKED | Existing renderers are reusable | Target default wiring/build remains absent |
| 20 | External producer and real three-entry validation | BLOCKED | No second methodology decision is required | No callable producer/real target exercise; implementation/runtime gap only |

`BLOCKED` on rows 17–20 denotes absent implementation/operational wiring only,
not a further methodology decision. The approved assumption boundary is row 15.

## Resolved historical blocker

`CORE_MVP_BLOCKED` was recorded on 2026-09-18 because loss/survival
qualification had no approved conditional boundary. It was resolved on
2026-09-18 by the user's explicit approval below. The historical conclusion is
retained; runtime implementation is not thereby complete.

## Approved assumption boundary

An explicitly identified conditional payment model, complete caller-supplied
cost upper bound/method, and explicit portfolio/repeat-loss policy may produce
`RESEARCHABLE_CONVEXITY`. The result is conditional-budget evidence only: it
never means actual safe loss, actual survival, or executable economics.
Unknown impact bounds remain `DSC_Core`; numeric, fee, ratio, and quantity
values are never system defaults. Exact-costs → RiskAssessment remains usable
only with its exact dependencies; raw `A` cannot create them.

## Approved BUILD boundary — API deferred

BUILD is authorized only for the approved conditional-model boundary above.
Direct, Discovery, and Event must preserve one common semantic Core, immutable
identity/lineage records, all-accepted-hypothesis branching, no human gate or
ranking, and the stated lazy-report/no-current-reference rules. Exact kernel,
application APIs, public type names, and record schemas are deliberately
deferred to the corresponding worker proposal and Main freeze; this document
does not invent them. No new numeric policy is introduced.

## Kernel implementation freeze — approved BUILD boundary

- Add independent `src/convexity_hunter/core_research.py` with
  `evaluate_core_research(CoreResearchRequest)` returning immutable
  `CoreResearchResult`; the three new dispositions do not overload legacy
  screening values.
- Each leg carries exact identity, Call/Put side, `K`, expiry, `q`, `m`,
  currency, optional ask, and provenance. A straddle requires the same
  underlying, expiry, strike, `q`, and `m` across both legs.
- This phase accepts only `CONDITIONAL_STANDARD_PAYOFF` with an explicit
  approval basis; it never claims verified deliverable terms.
- The cost ledger declares required components, an upper bound or `unknown`
  for each, completeness, and method. `premium_upper_bound` is total position
  cost and must be at least `Σ(q × m × ask)` when asks are present; it is never
  generated from asks, and explicit zero requires a stated basis.
- Portfolio value, maximum single loss, maximum repeated loss, and repeat count
  are all explicit. Sensitivity predeclares `S >= 0` and per-leg `ask > 0`.
- Any unknown required input returns `DATA_INSUFFICIENT_CORE` while retaining
  computable geometry. A complete case may derive `RESEARCHABLE_CONVEXITY` or
  `REJECT` from the budget; callers cannot pass a boolean approval flag.
- Output includes absolute gross 1x/2x/5x/10x hurdles, conditional loss and
  repeat stress, sensitivity, and authority. Enhancements never upgrade
  underpricing. Input identity and finite exact math are revalidated at entry;
  API details follow the implementation record. Main app freeze is recorded
  below.

## Main application freeze — BUILD boundary
- Target modules are `core_application`, `core_futu`, and
  `core_presentation`; this is a docs freeze, not a runtime claim.
- World raw requests enter through an injected bounded source producer. Event
  `UserEventInput` enters through an injected grounder. Both retain original
  input identity and emit source-backed Event Intelligence submissions; every
  submission is assessed.
- Every accepted hypothesis branches automatically through the existing
  maturity request, the Futu Browser's full supported-structure surface, and
  the common kernel. Automated provenance never fabricates human selection.
- Exact provider ID, rows, request, and batch identities bind together;
  multiplier is provider-supplied and quantity is explicit caller input.
- Operational bounds are explicit: exceeded runs retain `cases=()` rather than
  truncating; per-case exact failures are retained; quote-operation failure is
  a blocked branch with no retry.
- Direct runs real verification plus native quote through the kernel and then
  automatically produce the full report. World/Event produce `StructuredCaseSet`
  plus compact output; lazy reports reuse records and make no network call.
- The kernel remains independent of legacy `OptionStructure` and `ScreeningDecision`;
  every numeric policy is explicit and missing required input yields
  `DATA_INSUFFICIENT_CORE`/`DSC_Core`.
- Missing injected source is an operational blocker, never disguised
  code-complete result; no runtime completion is claimed, and app details remain
  subject to the corresponding worker/Main review.

At contract freeze, runtime was unchanged and no tests or real three-entry
exercise were claimed. See the dated implementation progress above for the
current state. An absent external callable producer is an implementation/
runtime gap, not a second user-authorization or methodology blocker.
