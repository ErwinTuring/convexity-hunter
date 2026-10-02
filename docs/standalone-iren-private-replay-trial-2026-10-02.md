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
