# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Required base for this contract freeze:

- branch: `main`
- HEAD: `8d743c517650d5bd3330e46240ed3c2ce7bec891`
- working tree: clean before this documentation-only change

Current work-unit subject:

`Freeze deterministic offline single-structure service contract`

This is an A-level documentation-only contract freeze. It does not implement
Python code or tests, change the package root, or authorize staging, commits,
or pushes.

Canonical contract:

- [`docs/offline-single-structure-service-contract.md`](offline-single-structure-service-contract.md)

The frozen service consumes one already-reviewed assembly result, always
screens it, optionally creates a caller-requested plan, and always renders the
Chinese report in the exact order defined by the canonical contract. Screening
and plan state remain separate; monitoring, alerting, scheduling, persistence,
and execution remain absent.

The next repository workflow gate is BUILD implementation and independent
focused testing of the frozen service contract. This freeze does not authorize
that implementation.

This file is a concise navigation map, not a complete specification or
history.
