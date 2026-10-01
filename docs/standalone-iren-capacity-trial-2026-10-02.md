# IREN capacity diagnostic preregistration — 2026-10-02

Status: **EXECUTED / SPENT — both calls completed; no EI acceptance.**

This independent protocol reuses only the reviewed CHECK runner mechanics in
[the prior CHECK trial](standalone-iren-check-diagnostic-trial-2026-10-02.md)
and the inherited transport protocol
[dated 2026-10-01](standalone-iren-transport-diagnostic-trial-2026-10-01.md).
Those runs remain spent; their runners, registrations, results and Main's
in-progress checkpoint/trial edits are unchanged.

## Registration and frozen state

RunID: `iren-transport-capacity-model-only-20261002-1fc6d6f80cf74ab29562930407c783fe`.

- Runner `/private/tmp/ch_iren_transport_capacity_2026-10-02.py`: 55,503 bytes,
  mode 0600, SHA-256
  `6247e9e84313a0891bd37838ce1b268bfc479b38462256902e14696695241dbc`.
- External prereg `/private/tmp/ch_iren_transport_capacity_2026-10-02.prereg.json`:
  4,193 bytes, mode 0600, SHA-256
  `9c5ea6dd0d5e9a26ef8a602a3c372c6d979a7bae5afc89243a0c712154d2fe1e`.
- New exclusive marker:
  `/private/tmp/.iren-transport-capacity-model-only-20261002-1fc6d6f80cf74ab29562930407c783fe.attempted`;
  absent during preparation; the runner claims it once with O_EXCL before
  runtime and never clears it.
- Production pin: `46876fda3473f72e43671040529bc3427f467047`; exact
  `src/tests` manifest SHA-256
  `101a92a4efd2788072409f6d000453a0561175ab41e6465428472dcd8fc01c0d`.
- Copied CHECK runner SHA-256
  `a6025c4e58473ec94042ec82592dc1bd87e54a3446cd77a4e02e02e6dddca9ac`.
  Safe transport helper remains pinned at
  `ecbe186fd5e85c4fdbb0c93ede0b0b4569415b372dc8be80605615ab494fb9b8`.

## Bounded delta

Only the fresh RunID/paths/marker and per-role token caps differ. Runtime
`ModelRuntimeConfig` is replaced at role-client construction with
`max_tokens=8000` for discovery and `6000` for semantic; the unchanged client
serializes that same config value. The safe aggregate and prereg state those
caps separately as `discovery_max_tokens=8000` and
`semantic_max_tokens=6000`, with no flat shared token cap. The closed
`failure_check`, stage/transport outputs, source/input/prompts/model,
preparer, failure behavior and other mechanics are inherited unchanged.

Each role retains one request, 45 seconds, 80,000 input bytes and 40,000 output
bytes; parser JSON remains 40,000 bytes. Catalog/source limits remain unchanged.
Source, retry, fallback and alternate calls remain zero. JSON mode stays on and
thinking stays off. No production/app default, fee flag, credential resolver,
prompt, source or test changes. Main verified the official API documentation's
8K non-thinking default; that is not an account-cap claim or completion
guarantee. A truncated response still has unknown usage unless a validated
transport receipt supplies it.

The runner requires the existing exact production/manifest guard and a distinct
docs-only descendant commit binding this RunID and both artifact hashes, plus
independent safety review and separate direct Main authorization. This
preregistration alone authorizes no invocation.

## Offline evidence

One offline run exited 0: external requests 0, credential resolutions 0,
synthetic runtime calls discovery 1 / semantic 1. Fake transports decoded the
actual serialized payloads and asserted `max_tokens` 8000 / 6000 respectively,
one-request configs, unchanged endpoint/JSON/thinking settings and byte limits.
A follow-up call for each exhausted budget without another transport request.
Synthetic oversized input, response and parser cases confirmed the existing
80,000 / 40,000 / 40,000 byte rejections.

Measurements: catalog 24,086 bytes (48 entries, 60 paragraphs, 12 nonunique,
0 overlong); full discovery request 48,499 bytes; semantic base 44,900 bytes;
synthetic full semantic request 60,859 bytes. The actual future semantic request
is producer-dependent and must pass the existing 80,000-byte guard. These are
offline measurements, not live usage or acceptance.

Inherited failure-check cases 37, transport composition 6, prereg gates 8,
code guards 12, preparer 8, source negatives 2 and exclusive-marker cases 2
passed. Minimal AST comparison against the CHECK runner: 22/25 existing
functions identical; only `measure`, `offline`, and `main` changed, with two
role-cap helpers added. No production or test file changed.

## Authorized one-shot result — 2026-10-02

After independent safety-review PASS, docs-only prereg commit/push
`199c32258b9251dcc4442543a95da01553f41ba3`, and separate direct Main
authorization, exactly one invocation exited 0. Both roles completed normally
(`finish_reason=stop`); `error_code`, `failure_stage`, `failure_check`, and both
transport error/status pairs are null. Each role used one reserved request;
source calls were 0 and preparer calls 1. No retry or fallback occurred.

| Role | Cap | Sent/received bytes | Prompt/completion/total tokens |
| --- | ---: | ---: | ---: |
| Discovery | 8,000 | 48,499 / 16,880 | 14,973 / 4,229 / 19,202 |
| Semantic | 6,000 | 77,262 / 13,484 | 21,836 / 4,049 / 25,885 |

Receipt validation completed. Producer counts: 17 claims (0 verified, 17
rejected), 0 hypotheses, 4 coverage records (all unresolved), and 0 field
bindings. Builder diagnostics: `CLAIM_REJECTED_BY_VALIDATOR` 17,
`FIELD_BINDING_MISSING` 39, `NO_PROJECTABLE_HYPOTHESIS` 1. No submission;
EI status is null. This is not an `ACCEPTED` result or product acceptance.

Rejected partitions mean the verifier did not support these producer claims;
they do not prove that the underlying public facts are false. The aggregate
does not retain their texts, outcomes or rationales. Discovery used only 4,229
completion tokens, below the old 6,000 cap; the independent output differed,
so successful completion cannot be causally attributed to raising the cap.

Exact sanitized stdout is retained at
`/private/tmp/ch_iren_transport_capacity_2026-10-02.result.json`, mode 0600,
3,252 bytes, SHA-256
`43b7a42a725ad53935a6d26a62c96c693608c3dd2303e0b61202576bba67c494`.
No raw response was retained. The attempt is spent. Specific offline next
step: map the existing producer validator and binding diagnostics against
synthetic fixtures; do not infer a particular live rejection or tune prompts.
