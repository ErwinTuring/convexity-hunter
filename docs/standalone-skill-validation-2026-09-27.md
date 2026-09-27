# Bounded Skill host validation — 2026-09-27

Scope: M1b native protocol controller and launcher, not a completed World
producer or an Event Intelligence adapter. No live Skill search or model call
was made in this work unit.

## Implemented and reviewed

`host_skill` drives the pinned last30days nominate/judgments/research/angles/
finalize handoff with full ID coverage, one directory/bundle, fixed seven-day
current-only policy and 3,600-second TTL. It does not rewrite expired bundles,
resweep, infer historical as-of results, or use native scores as Hunter authority.

Independent review identified missing native envelope checks and discarded final
output. Both were corrected and passed targeted re-review: precise native `1.0`
schema/kind, pending report/run reference, bounded native final JSON retained in
memory after temporary-directory cleanup. Optional explicit file output refuses
overwrite. Native research and nomination source items remain provisional;
publication dates are not invented from report dates.

The launcher disables known ambient config/keychain/password-store/model-auth
loaders and passes only explicitly granted source credentials. Existing authorized
ScrapeCreators Reddit and X credentials are supported; absent grants are not
read or passed. DeepSeek and other model credentials never enter this child.
This is a controlled known-code boundary, not a general OS sandbox or global
HTTP-request meter. Stage deadlines/output caps are not a per-source billing cap.

Pin covers the declared executable/protocol set, including imported Python and
vendored JS/MJS/JSON, rather than four entry files only. Current installed v3.21.1
content hash under this algorithm:
`74f97a97dcf4382bb4bf19521971bda4d6fbc09c2c0a656d1353eaf28e874920`.
Skill was not upgraded or edited. External interpreter/Node binaries are separate
runtime dependencies, not included in this Skill content hash.

## Independent local runtime

Installed CPython 3.12.14 from Astral python-build-standalone release `20260924`,
asset `cpython-3.12.14+20260924-aarch64-apple-darwin-install_only_stripped.tar.gz`.
The downloaded SHA-256 matched the [official release asset list](https://github.com/astral-sh/python-build-standalone/releases/expanded_assets/20260924):
`c2edb321cd32ec2b170df208db0446dccc4398db602ca27cf2079098fb1f7d9d`.

It is installed in the user's external application runtime directory, not Git or
the Codex runtime cache. The interpreter is configured by absolute path; no
system Python, Codex Python, global PATH, model or credential was changed.
No additional pip dependency was installed.

Offline validation: Python reports 3.12.14; SSL, SQLite, JSON and urllib import.
The real guarded launcher started the installed Skill with `--help` and no source
credential grants: exit 0, 13,431 stdout bytes, zero stderr bytes, no timeout or
output truncation. Output was counted/hashed rather than persisted. This is a
startup smoke check only, not a three-stage live discovery execution.

## Validation and remaining integration

15 focused synthetic tests passed, including protocol fixtures, malformed
envelopes, output retention, drift detection, TTL, full IDs and credential spies.
Compile and diff checks passed. The full suite, including the separate local
pre-Core gate worktree files, passed 1,512 tests on 2026-09-28. This suite did
not perform a live Skill discovery or validate Event Intelligence semantics.

Next: pre-Core input gate, semantic Grounder mapping/verification, model callback
wiring and a separately bounded real World execution. Source/semantic coverage
and operational budgets must remain explicit; no claim of standalone World,
Core or UI completion follows from this controller.
