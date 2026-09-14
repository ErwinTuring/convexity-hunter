# ResearchCase Application Composition Contract

Status: implemented as a bounded offline, in-memory application boundary.

This contract composes the existing product capabilities for one investigation.
It adds no persistence, UI framework, workflow engine, provider, market-data
formula, ranking rule, recommendation, or trade operation. `ResearchCase` is a
frozen application object that retains existing domain objects and reviewed
sidecars by identity; it does not copy or recompute their economics.

## Three entry modes

| Entry mode | Human checkpoint | Existing continuation |
| --- | --- | --- |
| Autonomous Discovery | candidate ID or explicit `None`, then hypothesis ID or `None` | `select_event_candidate` → explicit submission attachment → Event Intelligence → discovery handoff → option request |
| Event Entry | raw `UserEventInput` or prepared grounding, then hypothesis ID or explicit `None` | retained preparation/translation → Event Intelligence → option request |
| Direct Entry | exact user-supplied structure; no event thesis is invented | exact contract verification → reviewed research service |

The public composition functions are in
`convexity_hunter.research_case`: `start_*_case`, the two discovery/Event Entry
continuations, `attach_browser_evidence`,
`attach_discrimination_evidence`, `select_exact_structure`,
`verify_exact_structure`, `run_research_case`, and
`render_research_case_markdown`.

Every selection is explicit. A positive Autonomous Discovery candidate
selection is recordable on its own: it leaves the case awaiting an explicitly
supplied Event Intelligence submission and does not run Engine/EI assessment.
`attach_discovery_submission` then attaches that submission and runs the
existing assessment. Raw Event Entry likewise waits for an explicit
`EventEntryPreparation`; `attach_event_entry_preparation` retains the exact
`UserEventInput` before hypothesis selection. A selected candidate does not
select a hypothesis, one hypothesis does not select an option structure, and a
Browser row does not become a structure until the caller supplies its provider
identifier tuple. `None` is a human NONE checkpoint and stops that lane before
downstream work. There is no automatic selection, ranking, fallback
substitution, or single-item convenience default, and normal continuation
cannot advance a stopped or completed case.

## Retained lineage and downstream authority

Autonomous Discovery retains the exact `EventCandidateBatch`, selection,
translation, submission, accepted hypothesis, handoff, and
`OptionChainDiscoveryRequest`. Event Entry retains the exact
`UserEventInput`, `EventEntryPreparation`, hypothesis selection, translation,
context, and downstream handoff. Direct Entry retains the exact
`OptionStructure` and the caller's exact tuple of `OptionContractReference`
objects. The direct lane therefore has no invented event, hypothesis, or
maturity authority.

The Browser and discrimination stages are offline attachments. Browser evidence
must retain the exact option request. The pure
`discriminate_probability_free_convexity` result must retain that Browser.
Exact Futu selection must match one retained discrimination comparison. Exact
verification accepts only an already-created typed
`FutuExactContractSelectionVerification`. The application boundary has no
provider-context convenience branch and makes no provider call; an offline
fake context, when needed by tests, creates that typed verification outside the
application first. Neutral maturity retains the existing
`NOT_ESTABLISHED` alignment and its exact request identity.

After verification, all three lanes call exactly the existing
`run_direct_entry_reviewed_research_service`. That service remains the sole
authority for exact verification, optional readiness, reviewed-artifact
assembly, screening, optional position-management planning, and the Chinese
report. `ResearchCaseResearchInput` supplies the narrative, policy, and
partial or full reviewed artifacts, but cannot replace the retained structure,
contract references, or maturity context. The case summary reuses
`render_convexity_comparison_markdown` and the existing Chinese report; it is
not a second renderer for economics.

The scanner's existing hard-reject precedence is unchanged. A legitimate
hard reject may be returned before all six Engine gaps are complete; a
non-reject with missing required artifacts remains an honest
`DATA_INSUFFICIENT` result. `run_research_case` reports application
execution as `COMPLETED` once that one reviewed service returns, while
retaining the downstream `ScreeningDecision`, its missing-data reasons, and
its Chinese report. Empty Browser rows or zero discrimination comparisons
instead produce the distinct `NO_OPTION_RESEARCH_SURFACE` checkpoint; that
is neither a discovery rejection nor a human structure `NONE`.

## Current gap classification

The sprint separates product wiring from real evidence acquisition. The letter
is the mission classification: A = already implemented but not wired, B = can
be completed offline from existing authoritative inputs, C = code can be
prepared but real evidence needs RTH, and D = a new economic/methodology
decision. All six reviewed-result attachment paths are A and now wired.
No B claim is made: authentic real inputs have not been acquired here. C applies
only to future authorized RTH acquisition; external semantic authority remains
a separate dependency even during RTH.

| Engine gap | Classification | Current status | Existing transformation/input dependency |
| --- | --- | --- | --- |
| Structure costs | A | WIRED | The existing `StructureCostsTransformationResult` path is accepted and retained by assembly, screening, and report. A lawful non-missing result still needs authoritative contract, quote, and cost inputs. |
| Liquidity | A | WIRED | The existing `StructureLiquidityTransformationResult` path is accepted and retained. Provider activity/session, effective OI/volume, and quote semantics remain external evidence. |
| Volatility environment | A | WIRED; external authority required | `transform_volatility_environment` consumes explicit current/historical relationship selections, expected sessions, a realized-volatility result, and complete ATM candidate evidence. Futu IV/Greeks timing, model, and input semantics are not authoritative here; RTH alone cannot repair that. |
| Expiration tail slice | A | WIRED; external authority required | The existing tail transformation consumes volatility environment, current/historical relationships, expected session dates, complete tail candidate universes, historical EOD evidence, and explicit delta methodology. No reconstruction or synthetic completeness is added. |
| Target move scenario | A | WIRED; external authoritative inputs required | `transform_scenario_valuation` consumes explicit structure-cost and tail results plus a `ScenarioPricingCalculationResult`, scenario grid, and pricing methodology. Passing a result through is not an implemented pricing capability. |
| Volatility crush scenario | A | WIRED; external authoritative inputs required | The same existing scenario transformation requires an explicit reviewed scenario-pricing result and methodology. The app does not choose a crush method or manufacture prices. |

There is no active D decision in this sprint. Choosing a new IV estimator,
reconstruction method, or scenario pricer would be a new economic/methodology
decision and is intentionally unimplemented. Two lawful paths remain distinct:

- Earliest `REJECT`: a verified exact structure plus one sufficient authentic
  reviewed hard-limit artifact (for example liquidity), with its required
  dependencies, can trigger the existing hard-reject rule while other
  artifacts remain explicitly missing. Complete all-six evidence is not required.
- `WATCH` / `INVESTIGATE`: complete policy-critical costs, liquidity,
  volatility environment, tail, and required target/crush scenario evidence
  must satisfy existing dependency closure and screening policy, including
  assembly sidecars, affordability, and thresholds where required. Otherwise,
  absent a sufficient hard reject, `DATA_INSUFFICIENT` remains explicit.

Futu's supported indicative BBO does not establish canonical U.S. quote
time/session semantics. Provider `STANDARD` remains classification rather than
exact deliverable proof, and OI, volume, IV, and Greeks do not gain an
authoritative timing or methodology merely because the Browser is present.
RTH alone does not repair those semantic gaps. These boundaries are why an
offline composition test proves architecture, not market usefulness or a
non-`DATA_INSUFFICIENT` outcome.

## Product and experiment boundary

This sprint adds no live evidence and makes no investment claim. AMZN remains
paused without a selected structure, and the MSFT line is unchanged. The next
real completion work requires human selection, authorized RTH collection,
and authoritative evidence satisfying the documented semantic dependencies. Any
remaining D classification requires an explicit methodology decision before
implementation.
