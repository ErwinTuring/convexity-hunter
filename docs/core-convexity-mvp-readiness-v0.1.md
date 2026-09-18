# Core Convexity MVP Readiness v0.1

Status: `CORE_MVP_BLOCKED`
Decision: final Main readiness decision; documentation only
Decision date: 2026-09-18

This audit distinguishes method/input readiness from implementation. `READY`
means a method or reusable input boundary is available; it does not mean the
target runtime is implemented. The runtime/build column is explicit.

Pre-documentation baseline: fetched clean at HEAD
`7bd0cf1739b259ab247df47c9894486c802f59a9`; current changes are docs only.
Evidence environment: Futu API `10.10.7008` with OpenD `11111` listening; this
does not establish authentication, quote authority, or executable data.

Source anchors use full paths under `src/convexity_hunter/`: `event_discovery.py`,
`event_entry_preparation.py:219`, `research_case.py`,
`providers/futu.py:483,1356,2570`, `risk_assessment.py`,
`convexity_discrimination.py:769-859`, `convexity_presentation.py:60-61`,
and `report.py:1973`.

`READY_WITH_EXPLICIT_APPROVED_ASSUMPTION` applies only when the caller supplies
an already explicit approved assumption; it does not approve the pending
conditional-budget proposal below.

## Capability audit

| # | Item and evidence | Status | Method/input | Runtime/build state |
|---:|---|---|---|---|
| 1 | Supported Long Call/Put/same-strike Straddle model and three dispositions | READY | Scope is reusable | Target runtime not implemented |
| 2 | World/discovery intake caller: `src/convexity_hunter/event_discovery.py:148,248,319,412` | READY | Bounded records and provenance input | Current human-choice boundary; all-hypothesis target is build gap |
| 3 | Event Entry preparation: `src/convexity_hunter/event_entry_preparation.py:219` | READY | Identity-preserving input binding | Current explicit hypothesis selection; target no-gate bridge absent |
| 4 | ResearchCase: `src/convexity_hunter/research_case.py:213,707-708,873-875,1041` | READY | In-memory retained sidecars | Current manual/offline composition only |
| 5 | Direct exact-structure entry: existing direct-entry contracts | READY | Exact structure input is reusable | No target automatic full-flow claim |
| 6 | Futu exact verification: `src/convexity_hunter/providers/futu.py:483` | READY | Exact contract verification method | Auth/quote authority not established |
| 7 | Futu Browser: `src/convexity_hunter/providers/futu.py:1356-1359` | READY | Neutral eligible-row input | Existing manual browser; target enumeration not built |
| 8 | Futu quote batch: `src/convexity_hunter/providers/futu.py:2570-2576` | READY | Indicative ask input is reusable | Indicative only; no executable or timestamp upgrade |
| 9 | Existing maturity policies | READY | Reuses current policy | No new maturity policy implemented |
| 10 | Conditional geometry: `src/convexity_hunter/convexity_discrimination.py:769-859` | READY_WITH_EXPLICIT_APPROVED_ASSUMPTION | Conditional payoff math reusable | Not real payout or Core qualification |
| 11 | Existing gross hurdles and no-history absolute arithmetic | READY | Existing `M={1,2,5,10}` math | Current path still carries reference/runtime constraints |
| 12 | Exact costs → current RiskAssessment/`StructureCosts`: `src/convexity_hunter/risk_assessment.py:1138-1171,1329-1416` | READY | Exact dependency is reusable | Raw `A` cannot fabricate its dependencies |
| 13 | Fee/funding/settlement ledger | READY | Explicit ledger rule is reusable | Missing entries yield runtime `DSC_Core`, never zero |
| 14 | Portfolio/loss-budget inputs | READY | Caller inputs and no-default boundary | Missing required inputs yield `DSC_Core` |
| 15 | Loss/survival qualification | BLOCKED | True Core semantic blocker | Actual loss/survival is not established from indicative `A`, conditional standard payoff, and unknown costs |
| 16 | Premium-only acceptance | BLOCKED | No permitted method | Premium-only can never produce `RESEARCHABLE_CONVEXITY` |
| 17 | Conservative `DSC_Core` branch | READY | `DATA_INSUFFICIENT_CORE` rule is reusable | Missing policy instance may be runtime DSC, not a build blocker |
| 18 | All accepted hypotheses; no human gate/ATM-Delta/rank/Top-N/best | BLOCKED | Target method direction is explicit | Current selection path remains; missing target module is a build gap, not a second approval blocker |
| 19 | Default batch records: stable case ID, examined count, classification counts, reasons, compact rows, no prose; lazy detail | BLOCKED | Required output contract is explicit | New module/build item; no new market call except freshness policy |
| 20 | Renderers/producer/three-entry validation: `convexity_presentation.py:60-61`, `report.py:1973`, `research_case.py:1230` | BLOCKED | Existing renderers are reusable | No callable external producer or real target three-entry validation; implementation/runtime gap only |
| 21 | Quantity, multiplier, exact leg identity: `src/convexity_hunter/evidence.py`, `market_data.py` | READY | Explicit positive quantities and contract evidence are reusable | New Core binding must preserve identity; no implicit quantity default |
| 22 | Event Intelligence acceptance and temporal applicability | READY | Existing acceptance and maturity authorities remain unchanged | Automatic branching must consume accepted results, not auto-accept proposals |
| 23 | Repeat-loss policy: existing RiskAssessment contracts | READY | Caller-declared counts and loss-budget thresholds are reusable | No hidden default count or risk percentage; conditional budget qualification remains item 15 |
| 24 | Predeclared sensitivity | READY_WITH_EXPLICIT_APPROVED_ASSUMPTION | Caller-declared positive premium / nonnegative terminal-price scenarios support descriptive geometry | New Core computation/lineage binding required; no probability, carry estimator, or invented rejection threshold |

`BLOCKED` on rows 18–20 denotes absent implementation/operational wiring only,
not a further methodology decision. Row 16 records a prohibited shortcut, not
an input to obtain. The sole approval blocker is row 15.

## True Core blocker

With conservative non-inference, every branch with indicative `A`, conditional
standard payoff, and unknown cost or impact bounds is `DSC_Core`/
`DATA_INSUFFICIENT_CORE`. It may show a conditional budget only; it cannot
claim actual safe loss, actual survival, or executable economics. The existing
exact-costs → RiskAssessment path remains usable when its exact dependencies
are supplied; raw `A` must not be used to synthesize them.

## Smallest pending decision — not approved

User methodology approval is required to decide whether an explicitly identified conditional model,
complete caller-supplied cost upper bound, and declared method may qualify
`RESEARCHABLE_CONVEXITY`. Such a result must never be called actually safe or
executable; unknown impact bounds remain `DSC_Core`, and numeric or fee values
must never be system defaults. This paragraph is a proposal, not an approval.

Runtime is unchanged. No tests, real three-entry exercise, or code-complete
claim is made. An absent external callable producer is an implementation/
runtime gap, not a second user-authorization or methodology blocker.
