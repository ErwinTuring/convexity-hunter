# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Contract base:

- branch: `main`
- commit: `d34dd01e050b7f2d37624ef34f3293dd87db4fb1`
- subject: `Define offline single-structure service contract`

Finalized work-unit subject:

`Implement offline single-structure service`

The deterministic offline single-structure service is implemented and
independently reviewed. Its direct module and focused tests are:

- `src/convexity_hunter/offline_service.py`
- `tests/test_offline_service.py`

Canonical contract:

- [`docs/offline-single-structure-service-contract.md`](offline-single-structure-service-contract.md)

The service consumes one already-reviewed assembly result, always
screens it, optionally creates a caller-requested plan, and always renders the
Chinese report in the exact order defined by the canonical contract. Screening
and plan state remain separate; monitoring, alerting, scheduling, persistence,
and execution remain absent.

Independent review returned `IMPLEMENTATION REVIEW RESULT: PASS`. Final
validation passed 12 focused tests, 1,038 full-suite tests, compilation, and
`git diff --check`. The package root and all existing producer APIs remain
unchanged.

This file is a concise navigation map, not a complete specification or
history.
