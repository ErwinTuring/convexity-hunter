# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

## Grounded state

- Branch: `main`
- This checkpoint stores no static HEAD or parent SHA. A fresh thread must run
  `git fetch origin main`, `git rev-parse HEAD`, and
  `git status --short --branch`; Git is the sole code-state authority.

## Current executable boundary — 2026-10-02

Reviewed [IREN identity references](standalone-iren-identity-packet-2026-10-02.md)
are ready for the bounded Host key. The new [v0.5 product trial](standalone-iren-v05-product-trial-2026-10-02.md)
stopped at `PRODUCER_ENVELOPE_INVALID`, before semantic/Builder/EI. Its attempt
is spent; exact cause remains unknown. No live product acceptance is claimed.
The [closed producer diagnostics contract](host-grounder-producer-diagnostics-v0.1.md)
is frozen, implemented and independently reviewed. Sixty-one related tests,
compileall, API/signature compatibility, docs and diff checks passed; no new
full-suite run. Legacy behavior and acceptance gates remain unchanged.
No new live request is authorized by that diagnostic BUILD.
The separately preregistered [diagnostic trial](standalone-iren-producer-diagnostic-trial-2026-10-02.md)
subsequently ran once: `PRODUCER_ENVELOPE_INVALID` at
`producer_envelope_normalization / producer_wire_normalization`, discovery
reservation 1, semantic/source 0. No receipt/Builder/EI; exact normalization
subcondition remains unknown. Attempt spent, no retry. Next is a bounded
offline parser/binding-capacity audit, not another blind live request.
Core research still requires separately approved cost/risk policy inputs.

## Prior bounded work and approved target applicability

Latest narrow M2 unit: [Host context preparation v0.1](host-grounder-context-preparation-v0.1.md)
is frozen and implemented behind opt-in catalog runtime v0.2. Independent
review passed after constructor-bypass correction; 101 related tests and the
1,622-test full suite passed, plus compileall and diff checks. It permits
trusted, fill-only preparation after receipt validation, preserving run/input/
source authority. This resolves dynamic-ID handoff, not independent listing/
date verification or live product EI acceptance. Retained SEC source supports
IREN agreement date and a qualified future availability milestone; listing
identity and instrument currency still lack independent Host proof. No new live call
was made during its BUILD. A subsequent [preregistered IREN trial](standalone-iren-hypothesis-trial-2026-10-01.md)
called producer/verifier once each without refetch. Producer normalized 11
claims and one hypothesis; runtime stopped at `SEMANTIC_VERDICT_REJECTED`
before receipt/preparer/Builder/EI. Exact cause and semantic partitions remain
unknown. No retry; the spent trial's semantic stage remains unknown, not a
claimed live product acceptance.

Failure-stage diagnostics are now implemented: opt-in v0.2 can distinguish
wire parsing, receipt construction and pre-preparer receipt validation while
preserving the same rejection code and legacy stage `None`. Independent review,
13 focused/104 related tests, compileall and diff checks passed. The full suite
was not rerun for this diagnostic-only extension; its previous 1,622-test pass
predates the extension. Historical rejection stage stays unknown. The separately
[preregistered diagnostic trial](standalone-iren-diagnostic-trial-2026-10-01.md)
was authorized once after prereg commit and safety review. It stopped earlier:
`DISCOVERY_CALL_FAILED`, actual `failure_stage=null`, discovery1/reserved1
(18.138s), semantic0/source0. Usage and underlying reason are unknown; no
validated producer counts, receipt, preparer, Builder or EI followed. Exact
sanitized stdout is retained externally and hash-bound in the trial record.
Both attempts are spent; neither protocol permits another call. This
diagnostic execution did not reach or locate the old semantic rejection.
The independently reviewed external safe-transport helper and separately
[registered transport trial](standalone-iren-transport-diagnostic-trial-2026-10-01.md)
subsequently completed both role calls once. It failed at
`SEMANTIC_VERDICT_REJECTED`, actual `failure_stage=semantic_wire_parse`;
both transport code/status fields null. Producer11claims/1hypothesis/1binding/
4coverage are assertions only; receipt/partitions/preparer/Builder/EI remain
unavailable. Reported usage42,298 tokens; source0, no retry. This third attempt
is spent and does not retroactively locate either earlier failure. Next is
offline prompt/parser alignment review with existing synthetic verdict fixtures,
not raw live payload inspection, prompt tuning, validation relaxation or another
call. Exact parser rejection reason remains unknown. Bounded offline review
found no demonstrable prompt/parser contradiction; eight synthetic probes
respected the existing schema. The successor closed `failure_check` diagnostic
is now frozen and implemented after independent review: seven literal parser
check categories, opt-in v0.2 only, with unchanged public parser/legacy errors
and evidence gates. Sixteen focused/107 related tests, compileall and diff
checks passed; no full-suite rerun was part of that extension. Main later ran
the full regression at pinned production commit
`46876fda3473f72e43671040529bc3427f467047`: 1,628 tests passed in 296.423
seconds; the urllib3/LibreSSL warning was non-fatal.

After independent safety-review PASS and docs-only prereg commit/push
`199c32258b9251dcc4442543a95da01553f41ba3`, Main authorized exactly one
capacity-probe invocation. Discovery (cap 8,000) and semantic (cap 6,000)
both completed with `finish_reason=stop`, one reserved call each, and reported
usage 19,202 / 25,885 tokens respectively. `error_code`, failure stage/check,
and transport error/status fields are null. Source calls 0; preparer calls 1.
Receipt validated: 17 claims (0 verified, 17 rejected), 0 hypotheses, 4
unresolved coverage records, 0 bindings. Builder diagnostics were 17
`CLAIM_REJECTED_BY_VALIDATOR`, 39 `FIELD_BINDING_MISSING`, and 1
`NO_PROJECTABLE_HYPOTHESIS`; no submission, EI status null. This is not EI
acceptance. The one-shot attempt is spent, with no retry. Exact sanitized
stdout hash is in the
[capacity trial record](standalone-iren-capacity-trial-2026-10-02.md).
Receipt rejection alone cannot distinguish model non-support from deterministic
Host quote/binding/dependency rejection. Individual live outcomes were not
retained; their exact causes remain unknown. Next isolate those layers with a
separately preregistered synthetic calibration, not another product success claim.
The [two-date calibration](standalone-iren-semantic-calibration-2026-10-02.md)
passed six offline controls and independent safety review. After preregistration
commit/push and Main authorization, its sole model invocation passed: supported
May 29 / contradicted May 28, Host verified/rejected respectively. Model
coverage supported became Host unresolved due to the negative control. The
attempt is spent; this is not product Grounder or EI acceptance. Next inspect
producer/Builder binding compatibility and remaining independent Host evidence.
That preflight identified a prompt-completeness gap, not a recovered historical
rejection cause. The [binding clarification](host-grounder-context-preparation-v0.1.md#producer-binding-completeness-clarification--frozen-successor)
is implemented: internal catalog v0.2 dispatches/audits producer v0.5, while
v0.1 retains byte-identical v0.4. No gate or wire changes. Independent review,
33 focused/1,635 full-suite tests, compileall and compatibility/diff checks
passed. No live v0.5 run yet; independent listing identity/currency evidence remains
missing, and source/Host identity capability is the next bounded preflight.
That preflight confirms MIC is optional: `listing_mic=None` is lawful through
Host preparation, Builder and EI. Do not add a MIC-registry prerequisite.
Independent symbol/share-class/security-type and USD evidence is still required;
the retained SEC identity row has not yet been Host-reviewed and currency is
unproven. MIC remains unknown, not inferred from an exchange name or US prefix.
The [bounded identity source packet](standalone-iren-identity-packet-2026-10-02.md)
used one Tavily Basic Search (one reported credit). Both returned results failed
the frozen exact Nasdaq URL grammar; no Extract/body snapshot, retry or
fallback followed. This does not prove source/provider absence. The spent
attempt did not resolve USD trading currency or run model/Builder/EI/Core.
Separate offline review of the retained SEC body supports its IREN ordinary-share
cover row and registered exchange. Exact locations/hashes are in the source
packet record. This is limited Codex-assisted review, not current listing/USD
proof, a whole-body verification or an independent standalone Host capability.
The separate official-host source acquisition subsequently returned five Search
results and two Extract bodies. Its analyst-page title supports IREN ordinary
shares/symbol, but neither body proves explicit USD trading currency. The
`dividend-history` compound path escaped the history filter; scope deviation is
recorded, its historical/dividend data unused. Two requests/credits reserved;
one credit reported in aggregate. No retry, model, Builder, EI or Core followed.
The source record retains hashes and exact identity excerpts. This is source
retrieval plus limited Codex-assisted review, not standalone Grounder completion.
Subsequent single Yahoo-page Extract found IREN's `NasdaqGS - Delayed Quote•USD`
header. Initial literal-string checking missed that wording; targeted review
and independent body/hash review passed `READY_FOR_BOUNDED_HOST_KEY` for
`IREN / None / EQUITY / USD`, with provider-reported currency provenance joined
to issuer/Nasdaq share-class proof. No binding/EI run yet. This removes the
bounded identity-evidence gap, not the need for same-run semantic verification
or an independent general-purpose listing resolver. Next: one bounded v0.5
producer/Builder/EI trial using retained bodies, no source/quote calls.
That [v0.5 trial](standalone-iren-v05-product-trial-2026-10-02.md) is now spent:
after preregistration and exact-hash independent safety review, one discovery
reservation stopped at `PRODUCER_ENVELOPE_INVALID`; semantic/source calls 0.
Failure stage/check and receipt partitions are null; preparer/Builder/EI were
not reached. No retry or raw-output retention. Exact cause and usage remain
unknown. Identity readiness stays intact; next is a narrow offline
producer/parser alignment check, not another blind live request.

Current M2 boundary: [Host Grounder Builder v0.1](host-grounder-builder-v0.1.md)
is frozen and builder BUILD_READY after independent review. The closed DTO
parser, receipt identity/lexical validator, and deterministic Builder are
implemented, with 8, 16, and 13 focused tests respectively and independent
review. The Builder consumes the frozen validated envelope snapshot and can
produce a partial EI submission without dropping unrelated verified
hypotheses. It requires a trusted Host-produced semantic receipt. An internal
same-run Event path now makes a fallible verifier call, but live Host/source
production integration remains absent; structural/lexical checks
and synthetic receipts do not establish factual entailment or live EI
acceptance.

The [Host Semantic Validation v0.1](host-grounder-semantic-validation-v0.1.md)
contract is frozen and SUBSEQUENT_BUILD_READY after independent review and
targeted re-review. It specifies a separate bounded verifier call and
conservative evidence assessment, not semantic truth or EI acceptance. The
closed verdict parser and deterministic receipt-construction helper are now
implemented with 10 focused tests and independent review; in isolation they
do not authenticate the verifier call. The low-level Builder still accepts
mappings for controlled structural use. An internal same-run Event path now
uses pre-registered source bodies, separate bounded producer/verifier calls and
an internally constructed v0.2 receipt. A bounded internal catalog trial has
now completed both real model roles and returned a facts-only Builder result;
production source-acquisition integration, product Host integration and EI
acceptance remain open.

The [bounded internal Grounder live-trial record](standalone-grounder-live-trial-2026-09-29.md)
is the authoritative per-run chronology. Earlier quote-localization trial
(2026-10-01): the pinned
9,420-byte source returned (SHA-256 prefix `89536ce6ff75`); discovery
stopped normally (5,093 prompt, 1,860 completion, 6,953 total tokens; 5.619s;
`finish_reason=stop`). Producer localization failed at `quote_localization:106`:
static code raises `quote is missing` when a producer binding quote has no
exact occurrence in its registered body. The exact field/index/count are
unknown. Semantic was not called; no receipt or submission followed. No retry
occurred. Its cumulative Tavily reservations were 16, not settled usage or billing.

The [quote-localization contract](host-grounder-quote-localization-v0.1.md)
remains frozen. The explicit route uses producer/verifier wire v0.2 mapped to
strict internal v0.1, discovery/verifier prompts v0.3/v0.4, Semantic Validation
v0.3, and audit sidecar schema v0.2; receipt/Builder v0.2 and legacy behavior
remain unchanged. The prompt clarification is committed at `079ebb7`; 50
focused runtime/schema/model tests, compilation, diff-check, and Mill review
passed. The 1,602-test full suite last passed at `b759e24`, before that prompt
commit; it was not rerun.

The [Host Grounder Evidence Catalog v0.1 contract](host-grounder-evidence-catalog-v0.1.md)
is FROZEN and SUBSEQUENT_BUILD_READY after independent targeted review and Main
freeze. Its bounded implementation is now present behind a new explicit route;
70 focused tests and the full 1,612-test regression suite pass, along with
compileall and diff checks. Independent implementation review passed after
restoring the registered publication-metadata constraint in the new prompt.
Latest: a separately registered 32 KiB model-only trial consumed the retained
source without refetch, included all 48 eligible entries, completed discovery
and semantic, finalized audit, and returned 4 claims, 1 coverage record, zero
hypotheses and no submission. Both requests fit the unchanged 80 KB ceiling.
This is a completed internal facts-only mechanism, not EI acceptance or
product M2 completion. The trial log retains earlier source/capacity failures
and exact measurements. Cumulative Tavily reservations remain eighteen (not
billing); the model-only run added none.

Future Event run-input provenance is frozen in
[Run Input v0.1](host-grounder-run-input-v0.1.md), with reviewed contract deltas
in [Builder v0.2](host-grounder-builder-v0.2.md) and [Semantic Validation
v0.2](host-grounder-semantic-validation-v0.2.md). Pure input binding and an
internal v0.2 same-run runtime are implemented; public v0.1 Builder behavior
remains unchanged. No production product Host run has been established.

Latest continuation: [Sep27 Skill host validation](standalone-skill-validation-2026-09-27.md).
The pinned native protocol controller and guarded launcher passed independent
review, 15 focused tests and offline startup with independent CPython 3.12.14.
This is M1b startup and native output retention, not live World or EI acceptance.
The separate pre-Core gate passed review: invalid or empty source batches stop
before Core; valid incomplete submissions still reach EI. Full regression with
both implementation units passed 1,512 tests. Grounder remains open.

Earlier: [Sep27 Tavily transport validation](standalone-source-validation-2026-09-27.md).
The Sep25 unknown-field blocker was investigated with separately budgeted schema
diagnostics. Narrow Search/Extract compatibility fixes passed independent review,
19 source tests and a bounded real production-adapter Search/Extract run.
All returned evidence remains unverified; transport success is not Grounder/EI
acceptance. Skill execution work was subsequently reviewed. The
[Sep25 pause](standalone-host-resume-2026-09-25.md) is historical, not a current
quota or source-compatibility blocker.

Current work: [independent local MVP architecture](standalone-mvp-architecture-v0.1.md),
under the user's continuous M0–M8 authorization. This supersedes the old
Codex-hosted-only/no-UI/no-database delivery restriction, not EI/Core evidence
contracts. M0 targeted independent review passed; M1 transport/config BUILD is
unlocked. No production Host is claimed yet; M2 semantic acceptance is separate.
The user replaced local-model evaluation with an explicitly authorized DeepSeek
API. The local model was removed and its service stopped. One `deepseek-flash`
synthetic call succeeded (116 input / 19 output tokens); this is connectivity,
not semantic Grounder or independent-product acceptance.

M1a model transport/config is implemented in `host_model`, with independent
review, 18 tests, and one real production-adapter call (104 reported tokens).
It supports the user's existing external DeepSeek properties wrapper, explicit
remote/cost permission and budgets, no redirects/retry/fallback, and sanitized
receipts. Assistant content remains untrusted for the separate M2 semantic gate.
See [model validation evidence](standalone-model-validation-2026-09-24.md).
Controlled Skill execution, Grounder, persistence and the workbench remain open.

M3 Profile subunit is implemented in `host_profile`: explicit approved
USD100000 / .005 / 3 / .015, generated quantity one, immutable versioned snapshot
and the existing Core request factory. Verified multipliers/structure identity
remain unchanged. Independent review and 36 Profile/Core tests passed.
`cost_ledger=None` and `sensitivity=None` remain honest missing evidence; this
does not complete M3 cost/sensitivity work or standalone three-entry acceptance.

New World comparison: [Sep23 fresh run](world-source-comparison-2026-09-23.md).
The Sep17–23 native last30days run finalized within TTL: 15 nominations,
5 native themes, one source-qualified provisional SEC exemption candidate after
deduplication. Specific listed-symbol mapping is unresolved; this is not EI or
Core acceptance. Old Sep20 expired execution remains historically unchanged.
Web retained four provisional events; no retained event overlaps with the Skill
arm. Web exceeded its 12-open cap (24 requested URL items including a failed
12-item batch); this is a descriptive comparison, not a budget-compliant efficacy
test. No production source adapter was added. See the comparison for source-quality
limitations rather than treating native multi-source counts as proof.

Latest source work: [IREN semantic trial](event-grounder-iren-semantic-trial-2026-09-21.md),
using Sep 21 retained retrieval, continued offline Sep 23. Two searches and three
extracts succeeded. The verified financing subhypothesis is EI ACCEPTED with
no expected impact window; the procurement subquestion remains unresolved.
Independent execution review passed. Semantic evaluation is recorded in that report;
do not repeat the exhausted retrieval budget or treat retained data as fresh.

Earlier stage: [World/Event validation checkpoint](world-event-source-validation-2026-09-20.md).
The paid OpenAI Grounder route is withdrawn; Tavily free Search/Extract is
tested with PAYGO-off confirmed by the user's dashboard. Three Basic Searches
succeeded; two Extracts succeeded and the third workflow had a transport error
(request stage unknown; no retry). Search responses report three credits while
account usage still read zero at that earlier check. The later IREN precheck
observed those three credits; its own final usage snapshot was again not yet
updated. Do not claim settled remaining quota. Codex-assisted
verification must not be described as an independently deployed Grounder.

[Grounder semantic verification design](event-grounder-semantic-verification-design-v0.1.md)
is DESIGN_ONLY, independently reviewed with the empty-batch ambiguity resolved.
The proposed host stops before Core when no submission can be constructed;
this is not implemented production behavior. A subsequent bounded IREN trial
was explicitly authorized; it does not authorize a broader campaign or BUILD.

### Core application implementation — 2026-09-19

`core_research`, `core_application`, `core_futu`, and `core_presentation`
implement the approved thin application API. Kernel and application independent
reviews passed after targeted corrections to identity binding, retained report
reasons, early aggregate bounds, malformed native quotes, and exact-option
subscription. Twenty kernel and ten application tests pass; final regression
evidence is recorded in the [Core user flow](core-convexity-mvp-user-flow-v0.1.md).
Legacy Futu/discrimination public APIs remain 30/19; old valuation contracts
and manual-selection workflows are unchanged.

One real Direct technical smoke case completed via local OpenD on 2026-09-19:
AMZN 2026-11-20 K255 Long Straddle, one contract per leg. This is a disclosed
test input, not substitution for the historical human-selected structure.
Both exact contracts verified; two option quote reads were performed without
retry; all four owned contexts closed. Geometry and a Chinese report were
produced with `DATA_INSUFFICIENT_CORE`: `cost_ledger_missing`,
`risk_policy_missing`, `sensitivity_missing`. Quotes remain `INDICATIVE_ONLY`;
payoff remains conditional and maturity alignment remains `NOT_ESTABLISHED`.
No account safety, executability, underpricing or investment merit was proved.

World/Event application integration is tested with synthetic injected sources,
but live source adapters are not configured: runtime checks returned
`missing_source_producer` and `missing_grounder`. Do not call this three live
entry modes verified. Next operational work is source/grounder host wiring and
explicit caller cost/risk/sensitivity policy, not renewed theory or historical
option infrastructure. Missing policy must remain Core insufficiency, not a
hidden default. Optional VolEnv/Tail/history gaps are not Core blockers.

The [Core Convexity Research Doctrine v0.1](core-convexity-research-doctrine-v0.1.md)
is an accepted docs-only target correction, not a runtime or readiness claim.
Direct, Discovery, and Event entry target the same flow:

```text
uncertainty / event -> exact structures -> geometry -> cost/loss budget
-> sensitivity -> survival/repeatability
-> RESEARCHABLE_CONVEXITY | REJECT | DATA_INSUFFICIENT_CORE
```

Discovery and Event target all accepted hypotheses and deterministic eligibility
for supported Long Calls, Long Puts, and same-strike Long Straddles within
existing maturity policies. There is no target human selection gate,
ATM/Delta inference, ranking, Top-N, or “best” choice. Convexity is distinct
from underpricing and recommendation; missing history or optional
VolEnv/Tail/percentile/benchmark evidence does not invalidate Core. Required
portfolio/survival inputs and consumed fee ledgers are explicit and never
defaulted to zero. Absolute gross hurdles do not require history/reference.

The capability bullets below and later checkpoints describe unchanged current
runtime/legacy contract evidence. They do not claim the target has been built.
Readiness is `CORE_MVP_READY_WITH_APPROVED_ASSUMPTIONS`; see the [readiness audit](core-convexity-mvp-readiness-v0.1.md).
The approved application API is implemented; see the runtime qualifications
above. Existing legacy behavior is unchanged. Complete live three-entry
operation is not established.

## Product capability that exists

- The deterministic Convexity Engine, reviewed-artifact candidate assembler,
  screening policy, optional position-management plan, offline
  single-structure service, and Chinese renderer are implemented.
- Direct Entry separately verifies source-backed exact contract identity and
  complete research readiness. Missing authentic costs, liquidity, or other
  reviewed artifacts can truthfully produce `DATA_INSUFFICIENT`.
- Futu is the preferred MVP U.S. market-data provider. Tiger remains a frozen
  fallback capability; there is no automatic routing, failover, arbitration,
  or provider blending.
- The bounded Futu provider connects to an already-authenticated local OpenD
  instance and reads no credentials. It verifies one exact caller-specified
  monthly/provider-standard option, creates an incomplete provider-neutral
  contract reference, normalizes completed unadjusted underlying daily bars,
  and retains exact-option historical OHLCV, analytics/activity, and atomic
  option/underlying BBO as provider-native evidence.
- Existing Tiger local configuration, exact monthly verification, underlying
  history, dividend, historical-option, analytics/activity, and transient REST
  quote evidence remain unchanged and available as fallback evidence.
- U.S. Treasury daily par-yield retrieval and the bounded 30–180-day pricing
  rate proxy remain implemented.
- Bounded Event Intelligence capability research and the provider-neutral,
  Skill-neutral acceptance boundary are implemented. It retains structured
  sources, fact-versus-interpretation dependencies, resolved `UnderlyingKey`,
  impact and distribution hypotheses, inclusive methodologized windows,
  contradiction, uncertainty, falsification, and producer identity. Missing
  semantics remain deterministic `INCOMPLETE`; malformed identities,
  chronology, references, and graphs fail closed.
- Event Intelligence Temporal Semantics v0.2 is frozen and implemented. It
  preserves `expected_window` as expected impact, adds an optional atomic
  reassessment record for research governance, and keeps option-maturity
  authority separate. Structural-only acceptance does not establish aligned
  maturity: the compatibility/default aligned request fails with
  `missing_authoritative_maturity_anchor`, while only an explicit neutral
  structural request may open the Browser with `NOT_ESTABLISHED` alignment.
- Structural Narrative Option Research Activation v0.1 is contract-frozen and
  implemented and independently BUILD-reviewed. It uses one request plus a
  closed maturity-authority enum, preserves bounded-event behavior, and permits
  only an explicit neutral structural Browser with
  `hypothesis_maturity_alignment = NOT_ESTABLISHED`. One exact maturity-context
  sidecar is retained through selection, Direct Entry, and Chinese reporting
  without entering Engine evidence.
- The provider-neutral Event Discovery / Event Intake boundary retains at most
  ten provisional source-backed candidates under one explicit producer policy,
  preserves presentation order without ranking semantics, and records an
  explicit human choice of zero or one. Translation binds exact candidate and
  supplemental sources to one exact caller-built Event Intelligence submission
  but neither fills fields nor invokes acceptance.
- One repository-external SEC filing exercise produced an accepted AAPL
  submission with one source, two facts, one interpretation, and one
  bidirectional distribution hypothesis. It consumed no market data and
  persisted no raw external payload. The result did not justify an SEC adapter.
- The deterministic discovery-entry handoff retains one exact accepted Event
  Intelligence result and one caller-selected retained hypothesis by identity.
  It does not replay acceptance, select automatically, rank, retrieve a chain,
  or generate a structure.
- The provider-neutral option-chain discovery request retains the exact handoff,
  caller evaluation date, and exact maturity authority. Hypothesis-aligned
  requests derive `max(evaluation+30, event-end+30)` through
  `evaluation+150`; explicit neutral structural requests derive only
  `evaluation+30` through `evaluation+150` and retain `NOT_ESTABLISHED`. It calls no
  provider or clock and claims no contract eligibility. It derives
  applicability from the earlier complete expected-window or reassessment
  boundary, fails stale before arithmetic, and never extends a window. A
  current structural-only hypothesis using aligned authority fails with
  `missing_authoritative_maturity_anchor` because reassessment is not a
  maturity anchor; explicit neutral authority does not use it as one.
- The bounded Futu chain-evidence boundary retrieves expiration
  classifications once and one exact-date chain per in-range provider
  `MONTH`. It retains every valid row with deterministic applicability status
  and ordering. `MONTH + STANDARD + not suspended` remains provider-classified
  eligibility only; it completes no deliverable, settlement, reference,
  costs, liquidity, or research-readiness evidence.
- The bounded Futu Exact Contract Browser exposes all and only those
  provider-classified eligible rows from the authority-specific request bounds.
  It performs no provider call, ranking,
  labeling, or default selection. An explicit human selection creates only a
  listed-structure research intent; one Call or Put is supported, and a Long
  Straddle requires explicit same-expiry/same-strike Call and Put selection.
  The selection is not a candidate and cannot call Candidate Assembly.
- Probability-Free Convexity Discrimination v0.1 is Tier-A contract-frozen,
  implemented, independently BUILD-reviewed, corrected, and finally re-reviewed
  with no remaining finding. It preserves the exact neutral
  Browser, adds one separate pre-selection Futu provider-native quote batch,
  and displays exhaustive mode-compatible comparison geometry before explicit
  human selection. Ask-side metrics remain available when bid is zero or
  absent; relative spread alone requires two-sided evidence. Quote authority
  is `INDICATIVE_ONLY`, payoff authority is
  `CONDITIONAL_PROVIDER_STANDARD`, exact deliverable verification remains
  `NOT_ESTABLISHED`, and no comparison record can enter Candidate Assembly or
  close a current `missing_*` reason.
  A valid-RTH NDAQ experiment subsequently showed that Futu SDK 10.10.7008
  exposes protobuf `hpVolume` as Python `float`: all 164 received OrderBook
  rows otherwise parsed, but failed only as `ASK_SIZE_INVALID`. The corrected
  provider boundary accepts only exact positive non-Boolean `int`, or finite
  positive integer-valued exact `float` canonicalized to `int`; post-adapter
  evidence remains exact positive `int`. This explicitly corrects the original
  frozen raw-size assumption while preserving the canonical v0.1 evidence
  schema and all product semantics. Independent adversarial correction review
  passed with no finding.
  Production Futu now has exactly 30 direct-module exports and production
  `convexity_discrimination.py` has exactly 19; neither adds package-root
  exports. Final validation passed 45 focused tests and 1,370 full-suite tests.
  Exact checkpoint status: `IMPLEMENTED_AND_REVIEWED`.
  The first complete real NDAQ human checkpoint is recorded in
  [`probability-free-convexity-discrimination-real-experiment.md`](probability-free-convexity-discrimination-real-experiment.md).
  One valid-RTH batch covered 164 legs and 82 Long Straddles; all 164 legs had
  usable asks. The blind human selection changed from the prior neutral
  Browser-only structure to the 2026-10-16 97.5 Long Straddle, approximately
  65--70 structures were confidently rejected, and search effort was reported
  as materially reduced without probability estimation. This establishes
  `REAL_PRODUCT_VALUE_EVIDENCE = POSITIVE_BOUNDED`: one real NDAQ surface
  demonstrated human research-space compression. It does not establish
  repeatability, investment value, recommendation quality, maturity alignment,
  deliverable completeness, formal liquidity, synchrony, or executability.
- The pre-registered five-sample Hunter end-to-end validation campaign is
  complete. Sample 1 selected the AMZN advertising-auction lawsuit and
  terminated as `EI_NOT_ACCEPTED / missing_temporal_applicability`; its
  sanitized record is
  [`hunter-end-to-end-validation-sample-1.md`](hunter-end-to-end-validation-sample-1.md).
  Sample 2 selected the previously unknown APXT/TECfusions business combination
  with a new-to-human direct connection and mixed credibility. Supplemental SEC
  verification supplied a natural source-backed 2026-09-30 financial-statement
  reassessment milestone without inventing an impact end. Event Intelligence
  returned `ACCEPTED`, and the exact neutral 30--150 DTE request preserved
  `NOT_ESTABLISHED` maturity alignment, but Futu returned zero `US.APXT`
  expirations or contracts. Sample 2 therefore terminated as
  `NO_OPTION_RESEARCH_SURFACE`; its sanitized record is
  [`hunter-end-to-end-validation-sample-2.md`](hunter-end-to-end-validation-sample-2.md).
  Sample 3 selected the previously unknown TMQ Arctic Project permitting
  schedule and found both the event and direct project-to-underlying connection
  new and credible. A natural source-backed 2026-09-18 EIS milestone supported
  reassessment without becoming an impact end or maturity anchor. Event
  Intelligence returned `ACCEPTED`; the neutral Browser exposed 48 legs and 24
  Long Straddles across three expirations with `NOT_ESTABLISHED` maturity
  alignment. One valid-RTH quote batch supplied asks for all 48 legs, and the
  complete probability-free surface reduced human search effort but produced
  an explicit `NONE`: all 24 structures were rejected using indicative
  premium/reference and conditional payoff geometry. Sample 3 therefore
  terminated as `OPTION_RESEARCH_NONE`; its sanitized record is
  [`hunter-end-to-end-validation-sample-3.md`](hunter-end-to-end-validation-sample-3.md).
  Sample 4 selected the previously unknown PLUG Gateway-property-sale amendment
  and found both the event and direct balance-sheet/liquidity connection new and
  credible. A natural source-backed 2027-03-31 Gateway outside date supported
  reassessment without becoming an impact end or maturity anchor. Event
  Intelligence returned `ACCEPTED`; the neutral Browser exposed 64 legs and 32
  Long Straddles across three expirations with `NOT_ESTABLISHED` maturity
  alignment. One valid-RTH quote batch supplied asks for all 64 legs. The
  probability-free surface reduced human search effort, approximately 28 of 32
  structures were confidently rejected, and the human selected the
  2026-10-16 strike-2.0 Long Straddle as a deterministic-geometry research
  preference. Sample 4 therefore terminated as
  `OPTION_RESEARCH_PREFERENCE_FORMED`; its sanitized record is
  [`hunter-end-to-end-validation-sample-4.md`](hunter-end-to-end-validation-sample-4.md).
  Sample 5 selected the previously unknown IPW convertible-facility draw and
  found both the event and direct financing-survival connection new and
  credible. A natural source-backed 2026-10-01 first-payment milestone
  supported reassessment without becoming an impact end or maturity anchor.
  Event Intelligence returned `ACCEPTED`, but Futu returned zero `US.IPW`
  expirations or contracts inside the exact neutral bounds. Sample 5 therefore
  terminated as `NO_OPTION_RESEARCH_SURFACE`; its sanitized record is
  [`hunter-end-to-end-validation-sample-5.md`](hunter-end-to-end-validation-sample-5.md).
  The complete initial terminal distribution is one `EI_NOT_ACCEPTED`, two
  `NO_OPTION_RESEARCH_SURFACE`, one `OPTION_RESEARCH_NONE`, and one
  `OPTION_RESEARCH_PREFERENCE_FORMED`, with zero operationally inconclusive
  samples. The bounded synthesis is
  [`hunter-end-to-end-validation-campaign-synthesis.md`](hunter-end-to-end-validation-campaign-synthesis.md).
- The separately frozen five-sample extension is in progress under the exact
  unchanged protocol. Sample 6 selected the previously unknown Rocket
  Lab/Iridium cash-and-stock merger and found both the event and the direct
  RKLB transaction connection new and credible. Supplemental SEC verification
  supplied the source-backed 2027-06-28 initial outside date as a natural
  reassessment milestone without converting it into an expected impact end or
  maturity anchor. Event Intelligence returned `ACCEPTED`; the human retained
  the RKLB acquirer-side path, the neutral Browser exposed 296 eligible legs
  across three expirations, and discrimination mapped them exhaustively to 148
  Long Straddles with `NOT_ESTABLISHED` maturity alignment. One valid-RTH quote
  batch supplied asks for all 296 legs. The
  probability-free surface reduced human search effort, approximately 142 of
  148 structures were confidently rejected, and the human selected the
  2026-10-16 strike-65 Long Straddle based on equal surface-low
  premium/reference versus strike 60 but more balanced conditional 1x/2x
  geometry. Sample 6 therefore terminated as
  `OPTION_RESEARCH_PREFERENCE_FORMED`; its sanitized record is
  [`hunter-end-to-end-validation-sample-6.md`](hunter-end-to-end-validation-sample-6.md).
  Sample 7 selected the previously unknown ClearPoint/AMT-130 delivery-path
  hypothesis, found both the event and second-order connection new, and rated
  the transmission mixed. Primary materials established historical AMT-130
  trial use of ClearPoint navigation and SmartFlow cannulae plus current
  partner-program identification, but did not establish approved-label
  requirements, exclusivity, future per-administration use, procedure
  economics, volume, or enterprise materiality. A source-backed 2026-09-30
  four-year-data milestone supported natural reassessment without becoming an
  impact end or maturity anchor. Event Intelligence returned `ACCEPTED`; the
  neutral Browser exposed 74 legs across three expirations and discrimination
  mapped them exhaustively to 37 Long Straddles with `NOT_ESTABLISHED` maturity
  alignment. One valid-RTH quote batch supplied asks for all 74 legs. The
  probability-free surface reduced human search effort, approximately 33 of 37
  structures were confidently rejected, and the human selected the 2026-10-16
  strike-15 Long Straddle because its 1x/2x conditional hurdles were more
  bidirectionally balanced than strike 12.5 despite a slightly higher
  premium/reference. Its approximately 37.76% indicative relative spread
  remains a negative warning and no formal liquidity or executability finding.
  Sample 7 therefore terminated as `OPTION_RESEARCH_PREFERENCE_FORMED`; its
  sanitized record is
  [`hunter-end-to-end-validation-sample-7.md`](hunter-end-to-end-validation-sample-7.md).
  Sample 8 selected HUMA's V012 interim-result/financing combination; both
  event and connection were new and the human rated transmission credible.
  Event Intelligence accepted with a source-backed December 31 reassessment
  and no expected impact end. One RTH batch supported 23 neutral Long
  Straddles; the human rejected all 23 using premium/reference and 1x/2x
  geometry, with reduced search effort and no need for probability or spread.
  The terminal is `OPTION_RESEARCH_NONE`, useful negative compression within
  the indicative authority boundaries. See
  [Sample 8](hunter-end-to-end-validation-sample-8.md).
  [Sample 9](hunter-end-to-end-validation-sample-9.md) selected SUNE's Suniva
  reverse merger; event and connection were new and transmission credible to
  the human. EI accepted with no impact end and a source-backed Q4-end
  reassessment. A successful Futu chain query returned zero expirations and
  Browser rows: `NO_OPTION_RESEARCH_SURFACE`, not discovery rejection or
  option-geometry rejection. [Sample 10](hunter-end-to-end-validation-sample-10.md)
  completed with IREN October 16 strike 47 Long Straddle research preference
  after 190 comparisons, with approximately 175 rejected by the human.
  The [ten-sample synthesis](hunter-end-to-end-validation-ten-sample-synthesis.md)
  closes the extension. Stop for product synthesis; no automatic next sample.
- The separate selection-verification bridge revalidates one explicit Browser
  selection, invokes the existing exact Futu verifier once per selected leg,
  proves that every returned provider identity and economic contract field
  still matches, and applies the existing provider-neutral Direct Entry exact-
  contract gate. The sidecar preserves the exact selection, ordered provider
  verifications, exact references, and selected structure. It creates no
  candidate, research-readiness claim, service call, or orchestration layer.

## Live Futu evidence

On 2026-08-18, repository-external sanitized probes used the user's local
OpenD and persisted no raw payload. They confirmed:

- OpenD connectivity with U.S. stock level-3 and U.S. option level-1 rights;
- explicit monthly and provider-standard classification for one exact SPY
  option, provider multiplier 100, and American exercise type;
- a provider-neutral contract reference that deliberately remains
  `INCOMPLETE`, with no inferred OCC deliverable or settlement term;
- completed unadjusted SPY daily OHLCV and exact-option daily OHLCV history;
- populated exact-option volume, open interest, IV, Delta, Gamma, Theta, Vega,
  and Rho retained provider-natively;
- qualifying atomic option and SPY BBO frames with exact identity, values,
  sizes, and optional opaque provider timestamp-field values;
- one accepted AAPL source-backed discovery request producing 7 in-range
  expiration classifications, 5 provider-monthly exact-date chain calls, and
  880 retained provider-classified eligible rows (440 calls and 440 puts),
  with no raw payload persistence, quote retrieval, selection, or generation;
- one explicit human selection of the 2026-11-20 AAPL 295 Long Straddle from a
  neutral 15-pair Browser slice; both exact Futu leg verifications and both
  Direct Entry exact gates passed, both references remained `INCOMPLETE`,
  research readiness remained absent, screening returned `DATA_INSUFFICIENT`,
  and a nonempty Chinese report was produced without contract substitution;
  and
- the exact Futu contract entered the existing Direct Entry service without a
  new provider orchestration layer; exact-contract verification succeeded,
  research readiness remained absent, both candidate and screening states were
  `DATA_INSUFFICIENT`, missing costs/liquidity were explicit, no position plan
  was created, and a nonempty Chinese report was rendered.

No credential, account identifier, raw market payload, or secret entered the
repository or model output.

The AAPL discovery and Browser exercises above are historical pre-temporal-
gate evidence. Their 2025 expected window is expired for a 2026 evaluation
date, so the implemented gate now prohibits replaying that hypothesis as
current Discovery Entry. The downstream Browser/Direct Entry evidence remains
a historical implementation proof, not current-event applicability.

On 2026-08-24, a second repository-external sanitized exercise used the
official 2026-09-15--16 FOMC calendar and official SPY product identity to
produce one accepted, non-expired `BIDIRECTIONAL_EXPANSION` hypothesis with an
explicit 2026-09-16--23 MVP expected window. The temporal gate passed at the
2026-08-24 evaluation date. Futu exposed three eligible monthly expirations;
the user neutrally chose the nearest, 2026-11-20, then explicitly selected the
median strike from the displayed middle 15 pairs: one SPY 650 Long Straddle,
one contract per leg, USD 10,000 assumed portfolio value, and 30 calendar days.
Both exact Futu and Direct Entry gates passed without substitution; both
references remained `INCOMPLETE`, research readiness remained absent, and the
Chinese result was honestly `DATA_INSUFFICIENT`. Full sanitized evidence is in
[`futu-spy-fomc-browser-direct-entry-real-exercise.md`](futu-spy-fomc-browser-direct-entry-real-exercise.md).

The first bounded Web Search Event Discovery exercise is now complete and
recorded in
[`event-discovery-soc-real-exercise.md`](event-discovery-soc-real-exercise.md).
It produced nine validated candidates, the user explicitly selected SOC,
source-supported translation corrected a one-sided initial framing, and Event
Intelligence returned `ACCEPTED`. The resulting real SOC Browser selection and
Direct Entry path completed with an honest `DATA_INSUFFICIENT` Chinese report.

A second repository-external producer now applies only the event-taxonomy and
source-scanning portion of Anthropic's pinned `morning-note` Skill through the
unchanged `EventCandidateBatch` contract. Recommendation, Top Call, analyst,
rating, target, price-movement, positioning, scoring, and auto-promotion
semantics are excluded. Its same-window nine-candidate batch has validated;
the neutral comparison and explicit human result are recorded in
[`event-discovery-producer-comparison.md`](event-discovery-producer-comparison.md).
The user explicitly selected `NONE`: source quality was comparable, novelty
improved only slightly, and no unique Skill item supplied a sufficiently
credible research mapping. No translation, Event Intelligence assessment, or
Futu exercise followed. `morning-note` is retained only as a traditional
institutional-event baseline and does not replace bounded Web Search.

The authorized `last30days-skill` narrative/attention evaluation is recorded
in
[`event-discovery-last30days-evaluation.md`](event-discovery-last30days-evaluation.md).
The initial no-credential run is now classified `INCONCLUSIVE`: Reddit ended
`auth-failed` and X was absent. A properly enabled rerun used the new
2026-08-19 through 2026-08-25 window with repository-external X browser-cookie
authorization and ScrapeCreators-backed Reddit. Reddit, YouTube, and HN were
`ok`; X and Polymarket validly returned `no-results`; Web was `unreachable`.
The unchanged adapter discarded all native rank/score/recommendation semantics
and emitted a valid zero-candidate `EventCandidateBatch`. No human selection,
translation, Event Intelligence assessment, or Futu call was fabricated.
Material incremental discovery value was not demonstrated in this rerun.

The current 2026-09-20 World/Event source-validation run is a stage-level
blocked checkpoint, not a completed experiment; see
[`world-event-source-validation-2026-09-20.md`](world-event-source-validation-2026-09-20.md).
At `2026-09-20T23:47Z`, the native TTL had expired: leg 1 produced 15
nominations, leg 2 produced 5 pending topics, `read_pending_report` returned
`pending_valid=false; stale=true`, and leg 3 was stale after session interruption.
The final `EventCandidateBatch` is `NOT_COMPLETED`, not zero. Finalize exited 2;
no timestamp edit, source pull, rerun, or normal-finalize claim was made. Pending
source-relevance concerns remain limitations. Tavily credentials and free-only gate
are now resolved; see the linked checkpoint for real retrieval and remaining limits.

`Hunter Discovery Policy v0.1` is now frozen in
[`hunter-discovery-policy-v0.1.md`](hunter-discovery-policy-v0.1.md) without a
provider-neutral schema change. It defines one primary lane per candidate,
strict fact-versus-interpretation representation, an exact seven-day source-
publication window, and deterministic neutral producer ordering. The first new
window batch, 2026-08-11 through 2026-08-17, validated with nine candidates and
is recorded in
[`hunter-discovery-policy-v0.1-validation.md`](hunter-discovery-policy-v0.1-validation.md).
The user selected its `SECOND_ORDER_TRANSMISSION` NVDA power-financing item and
reported that both the event and connection were new, while credibility was
mixed. Supplemental NVIDIA evidence confirmed the explicit capital and limited
credit-support channel. Translation completed, but Event Intelligence correctly
returned `INCOMPLETE` only for `incomplete_expected_window`: sources provide
years and a lease term, not an exact end date. No date was inferred and no
market-data or downstream work ran.

The second new window batch, 2026-08-04 through 2026-08-10, independently
validated with six candidates after one provisional item was excluded because
an in-window primary source could not be verified. The user selected its
`NARRATIVE_BELIEF_SHIFT` NVIDIA compute-financing item and again reported that
both the event and connection were new, with mixed credibility. Supplemental
NVIDIA and Apollo evidence distinguished an aggregate capital-mobilization aim
from funded commitments and exposed independent underwriting plus possible
bounded NVIDIA residual-value support. Translation completed, but Event
Intelligence correctly returned `INCOMPLETE` only for
`incomplete_expected_window`; no exact end date was available or inferred, and
no market-data or downstream work ran.

The third new window batch, 2026-07-28 through 2026-08-03, independently
validated with eight candidates: five explicit catalysts and three narrative
or belief-shift rows. No second-order row was manufactured where the bounded
evidence did not support a transmission path. The user selected the IONQ /
SkyWater vertical-integration narrative and again reported that both the event
and connection were new, with mixed credibility. Supplemental SEC evidence
proved acquisition completion and `IONQ` / `XNYS` identity while preserving
SkyWater's continuing merchant-foundry role as contradiction evidence.
Translation correctly returned `INCOMPLETE` only for
`incomplete_expected_window`; acquisition completion supplied no exact end
date for integration impact, and no market-data or downstream work ran.

The first real
[`NEUTRAL_STRUCTURAL_RESEARCH` exercise](neutral-structural-research-real-exercise.md)
is complete. A new 2026-08-20 through 2026-08-26 bounded Web Search batch
produced eight candidates presented in neutral order; the user selected the
Nasdaq always-on-markets narrative and reported that both the event and
connection were new, with mixed credibility. A source-backed 2027-10-10
regulatory milestone supplied reassessment authority only, not an expected
impact end or maturity anchor, so Event Intelligence reached `ACCEPTED`
without hidden duration prediction. The neutral 30--150 DTE Browser exposed
162 NDAQ contracts across three expirations with `NOT_ESTABLISHED` maturity
alignment. The user selected the 2026-12-18 85 Long Straddle as a neutral
exercise structure. Exact gates passed, provider-neutral references remained
`INCOMPLETE`, and the final Chinese result remained `DATA_INSUFFICIENT` with
the maturity disclosure intact. This validates lawful structural-narrative
activation, not convexity-opportunity discovery; the user assessed Browser
usefulness as mixed.

## Current offline ResearchCase application boundary

The bounded immutable in-memory `ResearchCase` composition is implemented in
[`research-case-application-contract.md`](research-case-application-contract.md)
for Autonomous Discovery, Event Entry, and Direct Entry. Positive Autonomous
Discovery candidate selection can be recorded before any submission or EI
assessment; `attach_discovery_submission` attaches the caller's retained
submission separately. Raw Event Entry can likewise wait for a retained
`UserEventInput` to receive `EventEntryPreparation`. Candidate, hypothesis,
and exact-structure choices remain explicit, including human `NONE`, and a
stopped or completed case cannot advance through normal continuation.

Browser and discrimination evidence are offline typed attachments. Empty
Browser rows and zero comparisons terminate at `NO_OPTION_RESEARCH_SURFACE`,
which is distinct from discovery rejection and from a human structure `NONE`.
The app accepts only a typed
`FutuExactContractSelectionVerification`; it has no provider-context
convenience branch and makes no provider call. Any future authorized RTH or
other provider acquisition must create that typed verification outside this
application boundary. Neutral structural research retains
`NOT_ESTABLISHED` maturity alignment by exact request identity.

Once the one existing reviewed research service returns, application
execution is `COMPLETED` even when its independent `ScreeningDecision` is
`DATA_INSUFFICIENT`. Screening reasons, reviewed-artifact omissions, and the
Chinese report remain retained and rendered. This sprint added no live market
evidence and makes no investment claim.

## Current sanitized AMZN / historical-IV checkpoint

The durable documentation checkpoint is recorded in
[`amzn-pricing-evidence-checkpoint.md`](amzn-pricing-evidence-checkpoint.md).
It records the AMZN 2026-10-16 K255 Long Straddle partial Direct Entry result,
the unchanged six `missing_*` reasons, the native-only two-call historical-IV
rerun, and the conditional 2026-09-14 exact-DTE feasibility arithmetic. No
READY Engine evidence BUILD is claimed while supplier semantics and historical
expiry-universe authority remain unresolved; lookback/`D` sampling remains an
undeclared research-policy input. The later bounded caller RV assumptions below
do not change the provider or transformation contracts.
The [AMZN volatility-environment feasibility checkpoint](amzn-volatility-environment-feasibility-v0.1.md)
separates one-expiry-per-date 3C.7d history from Tail's matrix. The raw-close/252
caller RV policy and 22-session window are explicit; the single execution timed
out without a result, with no retry. Historical BBO/universe and current canonical
evidence remain unresolved; no provider or VolatilityEnvironment is proven ready.

## Current six-gap dependency/blocker split

All six reviewed-result attachment paths are A and now wired. No B completion
from authentic real inputs is claimed. C applies to future RTH acquisition;
external authority is a separate dependency which RTH alone cannot resolve.

| Gap | Classification | Current blocker and existing dependency |
| --- | --- | --- |
| Costs | A | The existing cost transformation and reviewed-service path are wired; authoritative contract, quote, and cost inputs remain external. |
| Liquidity | A | The existing liquidity path is wired; authoritative activity/session, effective OI/volume, and quote semantics remain external. |
| Volatility environment | A | The existing transform needs current/historical relationships, expected sessions, realized-volatility output, and complete ATM candidates. Futu IV/Greeks timing, model, and input semantics are not authoritative; RTH alone is insufficient. |
| Expiration tail slice | A | The existing transform needs volatility environment, session relationships, complete tail universes, historical EOD data, and explicit delta methodology. No reconstruction is implemented. |
| Target move scenario | A | The existing scenario transform consumes a caller-supplied `ScenarioPricingCalculationResult` and methodology; pass-through is not an implemented pricer. |
| Volatility crush scenario | A | The same explicit scenario-pricing inputs and methodology are required; no crush method is chosen or manufactured here. |

No D decision is active. A new IV estimator, reconstruction method, or
scenario pricer would require an explicit economic/methodology decision. Two lawful paths remain distinct:

- Earliest `REJECT`: a verified exact structure plus one sufficient authentic
  reviewed hard-limit artifact (for example liquidity), with its required
  dependencies, can trigger the existing hard-reject rule while other
  artifacts remain explicitly missing. Complete all-six evidence is not required.
- `WATCH` / `INVESTIGATE`: complete policy-critical costs, liquidity,
  volatility environment, tail, and required target/crush scenario evidence
  must satisfy existing dependency closure and screening policy, including
  assembly sidecars, affordability, and thresholds where required. Otherwise,
  absent a sufficient hard reject, `DATA_INSUFFICIENT` remains explicit.

## Active research-readiness gaps

1. Futu confirms U.S. real-time bid/ask/sizes, but explicitly does not support
   the two Order Book server-receive-time fields for U.S. securities. Populated
   numeric values remain provider-native and opaque. They and separate
   market-state reads authorize no event time, freshness, session binding,
   `OptionQuoteObservation`, `UnderlyingQuoteObservation`, or quote scope.
2. Futu's exact `STANDARD` classification is useful provider-native evidence
   but does not disclose exact OCC deliverable contents or corporate-action
   lineage. The provider-neutral contract reference remains `INCOMPLETE`, and
   the complete existing `StructureCosts` path remains closed.
3. Futu and Tiger volume/OI/analytics do not provide the required session,
   effective-date, analytics-time, model/input, Vega-scaling, and Theta-basis
   semantics. They do not authorize provider-neutral activity or Greeks
   observations.
4. Historical Futu option bars provide OHLCV but no historical bid/ask, open
   interest, IV, or Greeks. Missing derived series remain explicit rather than
   inferred.

These gaps block complete research-ready costs/liquidity, not the honest
partial Direct Entry loop. Canonical quote/session semantics, exact
deliverable proof, effective activity evidence, and IV/Greeks timing and
methodology are external-authority blockers; RTH alone does not repair them.

The six current screening gaps are frozen outside the Event Discovery / Event
Intake priority: `missing_costs`, `missing_liquidity`,
`missing_volatility_environment`, `missing_structure_expiration_tail_slice`,
`missing_target_move_scenario`, and `missing_volatility_crush_scenario`.
Freezing them preserves their fail-closed meaning; it neither removes them nor
authorizes inferred evidence.

## Next work

1. Treat the initial five-sample campaign and its
   [`bounded synthesis`](hunter-end-to-end-validation-campaign-synthesis.md)
   as complete. It produced five of five explicit human discovery
   continuations, four Event Intelligence acceptances, two legitimate option
   surfaces, one geometry-supported `NONE`, one geometry-supported research
   preference, and no operationally inconclusive sample. Its recommended
   extension to ten preserved the protocol, discovery policy,
   no-option-feedback rule, and human checkpoints, as frozen in
   [`hunter-end-to-end-validation-extension.md`](hunter-end-to-end-validation-extension.md).
   Samples 6--10 and the
   [ten-sample synthesis](hunter-end-to-end-validation-ten-sample-synthesis.md)
   are now complete. The separately authorized compact presentation BUILD is
   complete: `convexity_presentation.render_convexity_comparison_markdown`
   retains all comparisons in neutral order, reduces primary columns and
   provides a complete exact audit appendix (including non-comparison rows).
   No calculation, authority, ranking, selection or Engine change was made.
   Event Entry is now implemented separately in `event_entry.py`: user prose
   and unverified hints remain distinct from caller-grounded EI evidence;
   existing assessment and explicit hypothesis selection lead to the unchanged
   option request, with EVENT_ENTRY origin retained in sidecar context.
   No acceptance, maturity, provider, discrimination or Engine rules changed.
   `event_entry_preparation.py` now adds retained grounding and 0..N provisional
   hypothesis preparation, explicit human selection/NONE and identity-preserving
   translation into that existing service. No automatic search, temporal
   completion or realized-economic-impact prerequisite is added.
   The first real exercise stopped before EI with no testable underlying
   hypothesis selected; it was not system INCOMPLETE and did not test an option
   surface. This BUILD starts no new experiment and does not extend the campaign.
   See [current product state](project-state.md) for the exact boundary and record.
2. Treat the completed NDAQ discrimination experiment as one bounded positive
   product-value observation, not a reason to optimize the layer or claim
   investment merit. Preserve every indicative/conditional authority and add
   no ranking, recommendation, hidden maturity prediction, automatic Candidate
   Generation, or automatic unfreezing of the six screening gaps.
3. Treat the three-batch
   [`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md)
   repeatability exercise as complete bounded positive evidence. Do not add
   scoring, automatic promotion, or new discovery producers merely to improve
   this result.
4. Keep `morning-note` and `last30days` frozen as completed comparison evidence.
   Do not rerun or tune a Skill merely to force candidates.
5. Preserve the completed
   [`Event Intelligence Temporal Semantics v0.2`](event-intelligence-temporal-semantics-v0.2-contract.md)
   implementation and every historical result. Do not assign reassessment
   dates to the three prior structural cases, use governance dates as impact
   ends, or use them as option-maturity anchors.
6. Treat the real Futu-backed partial `DATA_INSUFFICIENT` report as the proven
   Direct Entry minimum slice. Keep costs and liquidity closed rather than
   inferring deliverable, activity, OI, IV, or Greek semantics.
7. Freeze further BBO timestamp probing and provider/rates/history expansion
   unless new official semantics or a future demonstrated product blocker
   justifies a separately bounded work unit.

## Explicitly deferred

- additional Treasury/rate sophistication;
- forward-dividend, historical-IV, and volatility-surface platforms unless a
  demonstrated vertical-slice blocker requires a bounded unit;
- automatic Delta/ATM selection, broad scanning, and structure generation
  until authoritative market semantics and a separate deterministic contract
  justify them;
- any Browser ranking, recommendation, default selection, or direct Candidate
  Assembly path;
- provider routing/arbitration, portfolio optimization, monitoring, alerts,
  recommendations, execution, and heavy orchestration frameworks.

Historical work-unit details remain in contracts, Git history, and the
historical ledger in `project-state.md`; they do not determine current
priority.
