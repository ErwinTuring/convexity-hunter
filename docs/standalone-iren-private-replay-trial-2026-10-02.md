# IREN private replay trial — 2026-10-02

## User-authorized retention boundary

The user explicitly authorized bounded private model-JSON retention for local
replay after the [schema observer trial](standalone-iren-schema-reason-trial-2026-10-02.md).
This changes only the next experiment's debugging retention policy; old
attempts remain spent and their missing payloads are not recoverable.

Persist only the discovery completion's content, at most 40,000 UTF-8 bytes,
outside the repository in a new 0700 directory / 0600 exclusive-create file.
Do not print raw content or copy it into Git, model prompts, reports or logs.
Do not retain credentials, request headers, private configuration, provider
response metadata or market payloads. The model input remains the approved
retained SEC public corpus; external credentials are resolved by the client
and are never model input. Semantic completion retention is not authorized.

The capture delegate preserves the original completion object, client config
and remaining budget. Non-string/oversize content is not written; capture
failure reports a closed status without payload or exception text. Original
runtime validation remains unchanged. Exclusive file creation prevents overwrite.
Offline replay may read this private content through local scripts and emit
only sanitized static validation categories and byte/count measurements.

## One-shot protocol

New run ID, runner hash, marker and result. Retain immutable prior helpers,
source/module pins, questions, model, limits and acceptance gates. DeepSeek
Flash JSON mode, thinking off; one discovery reservation/8,000 output tokens,
at most one semantic reservation/6,000, 45-second timeout each. No source
refetch, market data, Core, trading, retry or fallback. Unsupported expected
impact windows remain prohibited. No automatic bounds/schema relaxation.

Before live: actual default-offline PASS, independent exact-hash safety PASS,
preregistration commit/push and explicit Main authorization of those bytes.
Offline controls must cover literal captured UTF-8 bytes, no overwrite/modes,
non-string/oversize rejection and original result/config/budget identity.
No production changes are part of runner preparation or this policy.

## Frozen artifact and validation

Run ID: `iren-discovery-retention-20261002-ab55b3c3-c022-4137-a0ee-a2162bf0499b`.
Runner: `/private/tmp/iren-discovery-retention-20261002-ab55b3c3-c022-4137-a0ee-a2162bf0499b/runner.py`.
SHA-256: `07fda125682dbe628903157e1add4cd132a25e84af82200d0d9338a5caaf47c9`.
Immutable schema wrapper: `80c147fae75a8df8f5d375ac0faa67802982425aaf416bc79c886c59f75597f5`.
All inherited source/production/helper pins and limits remain unchanged.
Private capture target is `model-output.json` in that new run directory.
Directory/runner modes 0700/0600. Main reran offline preparation successfully:
nine new capture controls plus inherited controls, zero credentials/source/live
calls. No live capture, marker or result exists at registration. Capture rejects
non-string, oversize and non-UTF-8 text; write failure is reported safely and
does not alter runtime validation or authorize retry.
Independent exact-hash safety review passed. Reviewer inspected the nine
capture controls without rerunning their temporary writes; Main's actual
offline execution is the test evidence. No capture or secret was read.

## Actual one-shot outcome — attempt spent

After preregistration `ece201c` was pushed and Main authorized the exact hash,
one discovery reservation was consumed, semantic/source calls zero. Result:
`STOPPED / PRODUCER_ENVELOPE_INVALID` at `producer_v0_3_canonical_size`.
The schema observer was not invoked. No receipt, preparation, Builder, EI,
Core or market data. No retry. Native counts (13 claims, one hypothesis,
28 bindings, four coverage entries) remain unvalidated assertions.

Discovery content captured privately: 24,090 UTF-8 bytes, 0600 file at the
registered `model-output.json` path. SHA-256:
`cd2aa7b0506672f0f2fd4208afd129c67921fab5b88595a1342087c19a51e03e`.
Sanitized result (0600) in the same run directory, named `<run-id>.result.json`:
SHA-256 `e6d1909936e9a1f24bd37aab0916000836671090f856d5e8b6bf93cbcc8e2d5a`.
Marker remains; this attempt is spent. Capture is untrusted diagnostic input,
not evidence or a passed schema. Replay is offline and hash-bound; no raw
content enters repository or agent/model context.

## Hash-bound offline replay

For this capture, serialization succeeded and the normalized producer object
was **55,171 bytes**, 15,171 above the unchanged 40,000-byte limit. The exact
parser reproduced the same canonical-size rejection. Original exception
identity and observer restoration passed. This establishes overflow for this
capture only; it does not resolve prior trials' unknown causes.

The pinned 9,423-byte source yielded 48 catalog entries / 21,130 catalog bytes.
A separately labeled schema-only counterfactual used exactly 55,171 input
bytes, with the original 8,000-byte string and 64-item array limits unchanged.
It rejected the same expanded object. This is diagnostic, not product acceptance,
new runtime limits, receipt verification, Builder or EI. No model/source calls
or credential reads occurred. Subsequent precise schema analysis remains offline.

Replay directory:
`/private/tmp/iren-offline-replay-20261002-62bfa566-95cc-4360-a3f4-728d5126182d/`
(0700); `replay.py` and sanitized `replay-result.json` are 0600. Script/result
hashes will be recorded after the final bounded schema audit; intermediate
bytes are not claimed as a final reviewed artifact.

Final bounded schema audit identifies the first counterfactual failure:
`SCHEMA_STRING_TYPE_INVALID / CLAIMS_ENTITY_REFS_ITEM`. A claim's entity
reference item is an object where the existing schema requires a string.
The same expanded bytes were checked; no payload repair, value disclosure,
receipt or product acceptance. Independent targeted review confirmed the
validator frame/type and unchanged capture/result digests.

Final replay script SHA-256:
`d9e41855ce60afc7c4776afe5c6123961816d617e2911144abb519720cfba2d7`.
Final sanitized `replay-schema-rule-result.json` SHA-256:
`66f5b12079b1e9740aa0693e29a7e2afc35aa1638bca5f480eda7b93eded9543`.

Further preflight found a separate request-cap dependency: the same capture's
counterfactual semantic framing is 102,050 serialized request bytes versus
the current 80,000-byte client cap. This was pure framing, not a valid schema
or an actual semantic invocation. The producer prompt v0.5 names `entity_refs`
as an array with an empty example but does not specify its string item type.
The proposed fixes are a separately frozen finite caller resource profile
and an opt-in explicit item-type prompt; old profiles remain unchanged.
