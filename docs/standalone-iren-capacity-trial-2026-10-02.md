# IREN capacity diagnostic preregistration — 2026-10-02

Status: **PREPARED / OFFLINE PASS — NOT EXECUTED; no live authorization or attempt marker.**

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
role-cap helpers added. No production or test file changed, no commit was made,
and no invocation was attempted.
