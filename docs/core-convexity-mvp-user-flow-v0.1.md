# Core Convexity MVP User Flow v0.1

Status: Application API implemented and independently reviewed; live source wiring incomplete
Readiness: `CORE_MVP_READY_WITH_APPROVED_ASSUMPTIONS` ([readiness audit](core-convexity-mvp-readiness-v0.1.md))

This compact flow is governed by the
[Core Convexity Research Doctrine](core-convexity-research-doctrine-v0.1.md).
The implementation follows the approved conditional-budget boundary. It is
not a frontend, database or bundled autonomous search service.

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

There is no mandatory human selection gate in the Core Discovery/Event API, and no
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
screening states, and campaign records remain unchanged versioned evidence.

## Application API and host responsibilities

The thin application surface lives in `convexity_hunter.core_application`.
The host supplies a bounded source producer or event grounder, a market bridge,
and an explicit `CoreResearchPolicy`. This is not a bundled autonomous Web
search service. An absent producer/grounder is reported as an operational
blocker; prepared historical submissions do not prove live discovery.

```python
from convexity_hunter.core_application import (
    run_world_core, run_event_core, run_direct_core,
)
from convexity_hunter.core_presentation import report

# Dependencies below must already be configured by the host; no policy defaults.
world = run_world_core(
    raw_request, source_producer=source_producer,
    market_bridge=bridge, policy=policy,
)
event = run_event_core(
    user_event_input, grounder=grounder,
    market_bridge=bridge, policy=policy,
)
# Both return structured cases and a compact summary, not N prose reports.
summary = event.compact
cases = event.case_set.cases
if cases:
    detail = report(cases[0])  # Display request only; no new market-data calls.

direct = run_direct_core(
    exact_structure, exact_provider_bridge=bridge,
    direct_quote_evidence=None, policy=policy,
)
full_report = direct.full_report
```

`cases[0]` above illustrates explicit detail navigation, not an automatic
research preference. The default summary retains the complete neutral case
order. Callers normally choose a retained record by its stable `case_id`.

`policy.request_factory(*, case_id, structure, context)` supplies a kernel
request retaining the app-owned verified `structure` by identity. It may attach
explicit conditional-payoff, cost, risk and sensitivity inputs; it cannot
replace provider-derived identity, multiplier or ask evidence. Missing numeric
research policy produces `DATA_INSUFFICIENT_CORE`, not invented defaults.
Synthetic test policies demonstrate arithmetic only and are not user-approved
portfolio policy. An absent risk policy is distinct from a failed provider call.

## Real runtime evidence — 2026-09-19

Validation: 20 kernel tests and 10 application tests; full suite 1,454 PASS.
Independent kernel/application reviews passed after targeted fixes. The final
Chinese gross-value/cost disclaimer clarification also passed the application
suite. Compilation and local documentation links/fences passed; whitespace
checks passed. Existing Futu/discrimination exports remain 30/19;
new direct-module exports are Core kernel 30, application 14, bridge 8 and
presentation 6. Existing package-root/legacy production modules are unchanged.

The independently reviewed implementation was exercised once against the
existing local OpenD. The explicitly declared technical input was AMZN
2026-11-20 K255 Long Straddle, one contract per leg. This did not replace the
historical human-selected AMZN structure or imply a research preference.

- Two exact contracts verified, two option-only quote reads, no quote retry,
  four contexts created and four closed; no underlying BBO or trade call.
- Available conditional geometry and eight gross-hurdle result slots (including
  an unavailable negative-underlying threshold); a Chinese report was produced.
- Result: `DATA_INSUFFICIENT_CORE` for `cost_ledger_missing`,
  `risk_policy_missing`, and `sensitivity_missing`. No numeric risk/fee defaults
  were inserted. Historical VolEnv/Tail evidence did not block geometry.
- Quote authority stayed `INDICATIVE_ONLY`; conditional standard payoff,
  unestablished exact deliverable/maturity alignment and absent executable-price
  authority were not upgraded. Local receipt time does not establish freshness
  or a valid regular session.
- World/Event API checks with absent dependencies returned
  `missing_source_producer` / `missing_grounder`, with zero cases. These are
  honest operational-blocker checks, not real discovery or Event Intelligence
  success. Synthetic integration tests prove the configured three-entry wiring.

Only sanitized aggregate findings are recorded here. Raw provider payloads,
credentials, account information and the local numeric report are not committed.
The local report is `/private/tmp/core-mvp-direct-report-2026-09-19.zh-CN.txt`;
it is a presentation artifact, not the numerical source of truth.

### Remaining work and boundaries

- **Operational Core prerequisites:** configure actual host producer/grounder
  callables; supply explicit caller cost bounds, risk/repeat-loss policy and
  predeclared sensitivity to test a real qualifying Core case. Without them,
  retain blocked source lanes or truthful `DATA_INSUFFICIENT_CORE` records.
- **Optional enhancements:** historical valuation, VolEnv, Tail and benchmark
  claims remain separate and must not become prerequisites for Core geometry.
- No real `RESEARCHABLE_CONVEXITY` result, investment value or safe/executable
  position was established by this smoke test.
