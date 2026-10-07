# Local Event delivery v0.1

Contract status: FROZEN after bounded preflight. Implementation and independent
review are complete. Full regression passed
1,795 tests before narrow review fixes, final focused regression 114 afterward.
No real Event acceptance result is claimed.

## Existing authority

Reuse the [standalone architecture](standalone-mvp-architecture-v0.1.md),
[context preparation](host-grounder-context-preparation-v0.1.md), existing
Tavily Basic Search/Extract and DeepSeek transports, catalog v0.5 runtime with
v0.7 verifier, and the existing Event/Core application. No source summary is a
verified body; a semantic receipt is not EI acceptance.

## Trusted Host connection

An additive, explicitly configured Event Grounder receives the original input,
Host-owned run ID and explicit operational bounds. Existing callbacks returning
`CoreRunResult` retain their old signature and admission rules. Configuration
must not ambiguously enable both the legacy Event callback and the new path.

The run snapshot and Grounder stage start precede external calls. Each run uses
fresh bounded clients, with no automatic retry, fallback or unbounded search.
Search navigation order is not ranking authority. Extracted bodies are held in
memory, bound by identity/hash and checked against runtime bounds; snippets,
publication dates and model output cannot fill independent listing/date proof.
Missing evidence remains missing. Credentials stay outside Git and use existing
explicit resolvers; no credential contents or arbitrary executable paths enter
HTTP configuration.

A completed Grounder with no submission uses the existing atomic negative-stage
archive and terminates `BLOCKED / GROUNDING_NO_SUBMISSION`, without Core records.
A legitimate nonempty submission must be durably retained before downstream
market work. The narrow preflight passed; Main freezes the assessed positive
route below, reusing the existing closed EI codec rather than adding an
unassessed submission codec. The existing negative codec is not reinterpreted.
A restart interrupts
the run without replaying a potentially charged source/model request.

Only the existing deterministic EI assessor authorizes accepted hypotheses.
All accepted branches use the same Core service, Standard Research Profile,
explicit maturity authority and operational limits. Unknown costs/sensitivity
remain unknown; no ranking, human selection gate or opportunity claim is added.
Existing ordered batch archives and lazy Chinese details remain the output path.

### Positive-stage freeze

`save_grounder_submission_stage_result(run_id, stage_id, result)` admits only
the exact current evidence-catalog runtime result with one exact nonempty
`SourceSubmissionBatch`. Its raw input is the same object as Builder/context
input; its sole submission is the exact Builder submission. Original Host input,
run/input hashes, receipt/audit versions and completed-call metadata retain the
negative-stage checks.

The new closed `host-grounder-submission-stage-outcome-v0.1` retains the existing
bounded metadata, coverage, hashes and diagnostic counts, plus the closed typed
submission/assessment projection, its canonical digest and batch count of one.
The writer invokes the existing deterministic EI assessor; therefore
`submission_status=PRESENT` and `ei_status=ASSESSED`, with the actual assessment
status/issues retained. It does not assert `ACCEPTED` from model output. Source
status remains `UNKNOWN`. No raw source body, model response or credential is
stored. Existing EI snapshot encode/decode checks are reused.

Only the completed Grounder stage is appended; the Host run remains `RUNNING`
until downstream completion/failure. A crash preserves this assessed submission
and marks the run `INTERRUPTED`, without replay or a fabricated Core archive.
Generic stage writers cannot inject this DTO. Read-side admission rechecks its
closed shape, digest, exact EI semantics and original input binding. Negative
`host-grounder-stage-outcome-v0.1` stays unchanged, including atomic BLOCKED
termination. Existing schema-v3 events need no database migration.

Before model execution, source stops use the architecture's closed codes:
`NO_SEARCH_RESULTS`, `EXTRACTION_FAILURE`, `SOURCE_TRANSPORT_FAILURE` and
`OPERATIONAL_LIMIT`. Classified pre-Core stops are Host `BLOCKED`; unexpected
invariant/storage failures remain `FAILED`. Neither is Core `REJECT`.

Implementation-fit clarification: a missing/rejected external Tavily credential
also stops before Core as `BLOCKED / SOURCE_CREDENTIAL_UNAVAILABLE`. Only the
fixed Host code is retained, never the credential resolver's message or path.
This is a configuration gate, not evidence of a network failure or bad sources.

## Explicit configuration, not hidden product defaults

The source/model configuration supplies existing typed Tavily and two-role
DeepSeek settings, credential references, input/catalog limits and call budgets.
The Core connection separately supplies `evaluation_date`, the existing closed
maturity-authority enum and the Futu market bridge. Operational bounds come from
the immutable request. These are different inputs: a source budget cannot define
an economic policy, an observation timestamp cannot define a maturity anchor,
and a remote-model credential cannot authorize another provider or fallback.

Read-only integration preflight found that the shell's metadata validator admits
only empty model/source lists. Main therefore freezes one additive closed Event
configuration snapshot before transport: `models` contains discovery then
semantic, `sources` contains one Tavily entry, and `skills` stays empty. Legacy
empty shell snapshots remain valid. Models use
`host-event-model-snapshot-v0.1` plus the fourteen public `ModelRuntimeConfig`
fields (capabilities encoded as a list); source uses
`host-event-source-snapshot-v0.1`, provider `tavily`, the ten public source
budget/settings fields and `grounder_limits`. That limits object contains the
three exact run-input bounds and five explicit JSON/body/catalog bounds.
Credential references, paths, environment names/values and raw configuration
contents are excluded. The existing typed configuration validators are reused;
unknown/missing fields, swapped roles or non-authorized model settings fail
before any call. The trusted factory exposes this fixed projection through
`configuration_snapshot()`. Reading it does not resolve credentials or probe
any provider. The Host captures it in the immutable run-start transaction.

A context preparer must obey the existing independent listing/date evidence
boundary. A preparer that merely preserves unknown fields is lawful but cannot
be described as completed listing resolution or complete Event grounding.
The bounded [source-facts successor](host-event-source-facts-v0.1.md) permits
the default preparer to bind a unique verified description and narrowly
source-derived SEC occurrence date. It still resolves no listing identity and
does not establish complete Event grounding or real EI acceptance.
Any conservative stop on failed extraction is an acquisition limitation, not
proof that the event has no sources or no research value.

## Validation distinction

Transport-capable code, synthetic integration tests, a completed real Grounder,
EI acceptance and actual market/Core execution are separate evidence claims.
Until each is observed, it remains unproven. Default World capability is not
changed by this Event work. No prior spent experiment is replayed.

After focused validation and independent review, one new bounded integration
attempt may use the retained IREN financing/GPU research topic with freshly
acquired public sources: exactly one Event POST, at most one Basic Search and
one Basic Extract, one discovery and one semantic request. All limits remain
explicit configuration. No retry, alternate source/model, or market call to
improve coverage is permitted. A missing submission remains an inspectable
negative Host result. This is a new integration attempt, not replay of a spent
retained-packet trial or proof that historical facts remain currently applicable.

The new attempt uses evaluation date `2026-10-04` and the literal input
`IREN GPU/Dell/Microsoft project financing`, which is a research clue, not a
verified event statement. Explicit workload caps are one submission, four
hypotheses, 400 Browser rows, 200 cases and ten-second quote timeout. These are
operational ceilings, not economic selection rules. The existing approved
Standard Research Profile remains unchanged. Source ceilings are two requests,
three credits and five extracted URLs; model ceilings are one request per role,
45-second timeout, 8,000 discovery / 6,000 semantic output tokens. No new
expected window, listing identity or reassessment date is supplied by the runner.
The private experiment database is retained outside Git; only closed status,
reason codes and aggregate counts may enter the durable checkpoint. A spent
marker prevents repeat execution, including after partial transport failure.

First Host attempt ended `BLOCKED / SOURCE_CREDENTIAL_UNAVAILABLE` before Core.
Local resolver inspection found the stale `.env` reference absent; the existing
user-private `tavily.env.txt` parses successfully, as does the existing DeepSeek
configuration. No credential values were printed or persisted. The first private
database and spent marker remain intact. This is a local configuration failure,
not evidence about Tavily search or Grounder semantic quality.

One separately registered corrective attempt uses that existing credential file
with the same input, evaluation date and all source/model/workload ceilings.
It creates its own private database and exclusive spent marker. No retry of the
first artifact, increased budget, alternative provider, or evidence threshold
change is authorized. This continuation corrects configuration before the first
external acquisition; its outcome must still be recorded separately.

Corrective execution on `2026-10-05` (declared evaluation date still
`2026-10-04`) returned HTTP 201, `BLOCKED / SEMANTIC_VERDICT_REJECTED`, one
started/finished Grounder stage and no executor/Core result. The specific failed
wire/receipt check is unavailable: existing Host delivery retained only the
top-level reason. Do not interpret that as all facts rejected, EI INCOMPLETE,
poor source quality or a recovered raw response. No further call is part of this
spent attempt.

### Additive closed semantic failure diagnostics

Preserve the existing top-level reason and terminal status. For an exact
`HostGrounderRuntimeError` carrying `SEMANTIC_VERDICT_REJECTED`, Host delivery may
append only fixed codes for `semantic_wire_parse`,
`semantic_receipt_construction` or `semantic_receipt_validation`. For wire parse
only, it may additionally map the existing seven closed checks: `wire_decode`,
`topshape`, `run_binding`, `catalog_validation`, `producer_binding_alignment`,
`evidence_ref_expansion`, `internal_verdict_validation`. Unknown, inconsistent
values, including invalid attributes introduced through constructor bypass,
must not be serialized. Do not retain exception
text, payloads, paths, arbitrary keys or provider identifiers. This is diagnostic
delivery, not a new validator, automatic retry or retrospective result recovery.
The extra fixed codes belong to run diagnostics only. The Grounder stage keeps
its original admitted top-level code, preserving the existing closed stage
schema and historical read-side validation. Stage outcome and HTTP `reason`
remain unchanged; no Store schema migration or new endpoint is introduced.

### One diagnostic-delivery validation after the fix

One new independent attempt is preregistered after the diagnostic fix passes
73 focused tests and targeted re-review. It uses the same literal research clue,
source/model settings and operational ceilings, but declares evaluation date
`2026-10-05`. Existing private credential references remain external. Only the
new run can provide its own specific semantic failure codes; it cannot recover
the previous run's cause or establish that stochastic outputs are equivalent.
No query optimization, budget increase, model/provider change, raw response
retention, retry or acceptance relaxation is permitted. A separate private
database and exclusive spent marker are used. No extra attempt follows merely
to obtain better or accepted output.

Outcome: HTTP 201, Host `BLOCKED / GROUNDING_NO_SUBMISSION`. Grounder is
`COMPLETED`, semantic receipt `RECEIPT_VALIDATED`, Builder `COMPLETED`, submission
`MISSING`, EI `NOT_RUN`, source status `UNKNOWN`. Five bodies, fourteen claims,
zero hypotheses, eight field bindings and one coverage entry were retained as
bounded aggregate evidence. Builder diagnostic counts: rejected claim 12,
missing field binding 27, no projectable hypothesis 1. Coverage says model
`supported` but validator `unresolved`; a model's self-report is not authority.
There is no executor stage, case set or Core result. No additional call follows.
This new completed negative does not explain the prior semantic rejection or
prove that the diagnostic projection was exercised live; synthetic tests cover
that projection. Both private databases and spent markers remain preserved.
