# IREN transport-diagnostic preregistration — 2026-10-01

Status: PREPARED / NOT EXECUTED / NOT LIVE AUTHORIZATION. Await independent delta review, Main's prereg commit/push and separate direct authorization.

This independent attempt inherits the unchanged prereg mechanics from the [prior diagnostic protocol](standalone-iren-diagnostic-trial-2026-10-01.md), not its spent authorization. All prior runners, registrations and receipts remain immutable. No production/test/state edits, model/source/network calls or real credential resolution occur during this preparation.

## Registered delta and artifacts

RunID: `iren-transport-model-only-20261001-7ba56ba0465f41288b9bc9b6cfa8a84a`.

- Runner `/private/tmp/ch_iren_transport_model_only_v0_2.py`:45,686 bytes, mode0600, SHA256 `4574866aa080f20295703acbe1623283f50239073d094c1c73a100e2c85daa43`.
- External prereg `/private/tmp/ch_iren_transport_model_only_v0_2.prereg.json`:3,865 bytes, mode0600, SHA256 `5122f019611e68f292e8e13d4f66dc72f42076439e563f64f6257f862d55a2e1`.
- Reviewed helper `/private/tmp/ch_safe_model_transport_diagnostic_v0_1.py`:SHA256 `ecbe186fd5e85c4fdbb0c93ede0b0b4569415b372dc8be80605615ab494fb9b8`; Main reports independent review PASS. Runner verifies this hash before import.
- New exclusive marker `/private/tmp/.iren-transport-model-only-20261001-7ba56ba0465f41288b9bc9b6cfa8a84a.attempted`:O_CREAT|O_EXCL0600, never clear/retry; absent during preparation.

Copied spent runner SHA256 `eed6bd6a929b248031b3ba07ca58707e83d96b8455dc303e46a3fc639ef6148b`. Changes only independent ID/files/marker, reviewed mixin composition, null safe-field initialization, changed-ID byte measurements and deterministic offline checks. Same source/input/subquestions/prompts/Deepseek-flash/budgets/v0.2 opt-in route and trusted Host preparer; no prompt tuning or new acquisition.

Mixin wraps the existing metered client. Exact ModelTransportError only;30 explicit existing static host_model codes, exact int HTTPstatus100..599 excluding bool, otherwise null. Fields are independently filtered. Record only role-specific transport code/status, then re-raise the same exception; no extra calls or behavior change. Existing closed failure_stage still reports an operation, not an underlying reason. Unknown usage/partitions remain unknown until captured/validated. No exception text/args/locals, arbitrary strings, request headers, raw response or secrets. This cannot recover any previous unrecorded transport code or old unknown semantic stage.

## Gates and bounds

Pin production `72e72f7ceb1c52ae78b498bba4589d8356a850b8`, exact src/tests manifest `38e33e4e92315170ad71b57955d0163b166a540254116d372176067c19532dad`, docs-only descendants/worktree/index/nonignored untracked paths. Existing reviewed-helper pins remain. Before any live preparation, require Main's separately authorized `--model-only --prereg-commit <fullSHA> --main-authorized`; supplied distinct docs-only descendant commit must be ancestor of HEAD and include this protocol binding current RunID/runner/prereg hashes. Flags alone confer no authority. Runner/prereg contain no future commit or circular self-hash.

One producer + at most one verifier; source0/retry0/fallback0. Catalog32KiB, entries64/paragraphs128/arrays64/string8000; input80000/output40000 bytes,6000tokens/45s per role, JSON mode/thinking disabled. Other parser/source bounds inherit the prior protocol. Identical retained F1 body9,423 bytes/SHA256 `00ecc509846b657702081827db78a220b8ff51a9bacd19537339575e17ee6e29`, historical retrieval and independently reviewed agreement-date anchor unchanged. Missing independent MIC/trading-currency proof stays explicit; partial EI/facts-only zero hypothesis remain lawful.

Exact local measurement:48 catalog entries,60 paragraphs (12nonunique/0overlong); canonical catalog24,077 bytes; full discovery48,481; semantic base(empty envelope/hash64)44,882; synthetic full semantic60,832. The shorter new RunID accounts for changed byte lengths. Unknown actual semantic envelope must pass the unchanged80KB guard before calling; fit is not guaranteed.

## Offline validation

Syntax PASS;14 original mechanics functions exact AST unchanged, model-only function exact after only client-factory substitution. Default fake runtime PASS:producer1/verifier1, external requests0, real credential resolutions0. Reviewed helper53 cases PASS; actual mixin+metered-wrapper composition6 cases PASS (same exception, single fake call, success receipt identity and existing timing/metering preserved). Existing stage10/prereg-gate8/code-guard12/preparer8/source-negative2/exclusive-marker2 cases PASS; oversized request guard preserved. Synthetic EI incomplete is composition evidence only, not real entailment or live acceptance.

Stop on any future failure; preserve only sanitized stdout and available audit-stage booleans, no raw payload retention. This document authorizes no execution or retry. Main chooses the next step after independent delta review and registration commit.
