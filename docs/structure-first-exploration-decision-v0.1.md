# Structure-first exploration: bounded authorization decision v0.1

Status: **APPROVED / FROZEN — BUILD in progress, not live-validated**.

The user approved this authority and neutral 30–150 calendar DTE policy on
2026-11-19, after independent review passed the bounded decision package.
This is not approval for new paid/provider experiments.

## Accepted product direction and current runtime

The user requests structure-first Event/World research. A complete directional
explanation or EI acceptance must not be a universal prerequisite for researching
an independently verified exact structure. EI remains the authority for specific
event/distribution claims, not for the mathematical existence of convexity.
The subsequent explicit approval authorizes the additive authority below.

Grounded base: `e2586b82a4858a369d56defa4ed249710dbe5338`; HEAD/main/origin-main
matched and the worktree/index were clean. No external research was run.

The current runtime cannot express the requested exploration honestly:

- `core_application._run_source_core` stops each non-ACCEPTED submission before
  creating a request. This is the application routing gate to separate.
- `DiscoveryEntryHandoff` requires an accepted result and an exact retained
  hypothesis. `OptionChainDiscoveryRequest` requires that handoff, a resolved
  underlying, a distribution mode and the frozen temporal authority.
- Both existing maturity authorities require EI ACCEPTED. Neutral structural
  research additionally requires complete reassessment and no expected window.
- Futu request validation and Core context validation reconstruct those exact
  records. Removing only the application's `continue` cannot bypass them.
- Enumeration currently uses distribution mode to select Calls, Puts or paired
  Straddles. Unknown direction is NOT BIDIRECTIONAL_EXPANSION.
- Host listing preparation currently obtains independent listing evidence but
  projects it through a verified hypothesis-symbol binding. That projection
  must be separated from full hypothesis readiness, not replaced by ticker trust.

The original contracts are [discovery request v0.4](option-chain-discovery-request-contract.md)
and [structural activation v0.1](structural-narrative-option-research-activation-contract.md).
Direct already calls the common Core without EI; its authority convention and
existing behavior must remain unchanged in this work unit.

## Approved minimum authority change

Add one new, explicitly requested authority:
`EXPLORATORY_STRUCTURE_RESEARCH`, with an inclusive **30–150 calendar DTE**
interval calculated only from an explicit evaluation date. This is approved
research policy, NOT an event impact window or duration
estimate. No reassessment date or expected window is manufactured. Alignment
always remains `NOT_ESTABLISHED`.

Use a distinct `ExploratoryOptionChainRequest` alongside the unchanged accepted-
hypothesis request. Its input is a validated exploration lead plus the explicit
policy/evaluation date. Do not make the old handoff optional, fabricate an
ACCEPTED result or use Direct as an unlabelled authority bypass. Both request
types feed the SAME Futu retrieval, Browser, quote/exact verification and Core.
Type dispatch must be closed and intrinsically revalidated at trust boundaries.

The lead must retain, by auditable linkage to existing admission/verification
records: a supported event/change fact and source identity; observation time;
independently verified security/listing/currency identity; a source-supported
entity/exposure link; the explicitly provisional economic relevance explanation;
and unresolved questions. A raw URL, typed ticker, JSON shape, model confidence,
or merely admitted page is insufficient. Lack of directional/distribution proof
does not invalidate that narrower link. This uses the existing verifier and
listing composite, not new inference, string matching or another model stage.

Exploration is explicit opt-in under existing finite operational bounds, not a
fallback applied to every news item. Policy activation is application
configuration, not a new mandatory per-event human selection checkpoint.
Existing lawful accepted-hypothesis routing
and stronger maturity constraints take precedence; a stale/invalid accepted
handoff cannot silently fall back to exploration. No automatic refresh, roll-
forward, new numeric budget or paid execution is authorized by this proposal.

For each eligible Browser surface, enumerate all supported singleton Calls,
singleton Puts and unambiguous same-expiry/same-strike paired Long Straddles in
deterministic navigation order. Do not infer direction or filter by a fabricated
distribution mode. Preserve unavailable rows/reasons; enforce existing total
row/case limits without Top-N truncation, scoring or ranking.

## Frozen additive interface boundary

`ExplorationLead` retains `lead_id`, `event_description`, aware `observed_at`,
exact `underlying_key`, source/statement tuples, `event_statement_id`,
`exposure_statement_id`, `underlying_reference`, `validation_reference` and an
explicit uncertainty tuple. Source/statement records reuse existing EI evidence
types but are NOT an EI submission or accepted hypothesis. Event evidence must
be an observed fact. Exposure must have verified subject binding and a complete
source/dependency closure; a directly relevant own-issuer fact may witness both.
An interpretation remains labelled as interpretation. Public record construction
checks intrinsic structure, not semantic truth; normal Host projection must
independently validate the existing receipt, sources and listing proof.

`ExploratoryOptionChainRequest(lead, evaluation_date)` derives exactly the new
authority and NOT_ESTABLISHED alignment. It does not accept a distribution mode,
expected window or reassessment. Both request types retain identity through the
same Browser and Core path and reject constructor-bypassed invalid instances.

`SourceSubmissionBatch` gains a default-empty `exploration_leads` tuple;
`CoreResearchPolicy` gains a default-false `exploration_enabled` flag. Existing
positional constructors remain compatible. The Host enables the policy only by
explicit application configuration (`--enable-exploratory-research`), not a
verified-evidence field supplied in user POST. A batch may contain independent
leads without any EI submission; do not construct a placeholder hypothesis to
satisfy the EI constructor. No lead means no new market request.

Persistence uses a closed additive archive version for exploration runs, keeping
old readers/records compatible and retaining lead identity, evidence references,
independent EI status and authority disclosure. It stores structured records, not
raw responses, full source bodies or pre-generated prose.

## Interface impact and smallest BUILD

1. `option_chain_discovery.py`: add the explicit exploration request/authority
   and narrow validated lead; preserve old constructors/defaults. Update the
   frozen request/activation contract with an explicit additive successor.
2. `host_event.py` / existing Builder preparation: expose independently verified
   event/entity/listing evidence without requiring a complete economic hypothesis.
   Missing evidence stops before market access; no prefilled submission.
3. `providers/futu.py` / existing market bridge: accept the closed new request
   type through shared retrieval/validation. Preserve MONTH/STANDARD, suspension,
   exact identity, quotes and provider authority restrictions.
4. `core_application.py` / `host_event_core.py`: add the explicit exploration
   route and neutral all-three-grammar enumeration; retain exact source/request
   provenance. Reuse the existing kernel factory/evaluator and risk/cost policy.
5. Existing archive/Workbench/Chinese renderers: separately retain and display
   exploration admission, maturity authority/alignment, EI claim status and Core
   classification. EI INCOMPLETE never becomes supported; it does not erase
   lawful geometry. No full prose batch generation or second persistence system.
6. World reuses the same Event exploration route after the Event slice passes;
   Direct and legacy EI ACCEPTED paths receive compatibility regressions only.

Focused acceptance: credible direction-unknown lead proceeds; unverified source,
identity or exposure cannot call the market bridge; actual component fixtures
produce geometry; missing mandatory cost/loss evidence prevents Core qualification;
EI INCOMPLETE is preserved; Direct and accepted routes remain unchanged. One
independent review; no new paid/provider trial in this work unit.

The explicit approval resolves the original authority blocker. BUILD must now
deliver the integrated path rather than unused helpers. Historical records and
the previous runtime are not retroactively reclassified by this contract.
