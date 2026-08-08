# Current Checkpoint

Repository: `ErwinTuring/convexity-hunter`

Contract base:

- branch: `main`
- commit: `74f2698`
- subject: `Define direct-entry reviewed research service contract`

Finalized work-unit subject:

`Implement direct-entry reviewed research service`

The Deterministic Direct-Entry Reviewed-Research Service is implemented and
independently reviewed. Its direct module and focused tests are:

- `src/convexity_hunter/direct_entry_reviewed_research_service.py`
- `tests/test_direct_entry_reviewed_research_service.py`

Canonical contract:

- [`docs/direct-entry-reviewed-research-service-contract.md`](direct-entry-reviewed-research-service-contract.md)

The service composes exact-structure verification, the existing 21-argument
candidate assembler, and the existing offline screening/plan/Chinese-report
service. It preserves delegated object identities and error order without
adding local eligibility, numerical, lineage, or policy authority.

Independent review returned `IMPLEMENTATION REVIEW RESULT: PASS`. Final
validation passed 11 focused tests, 1,059 full-suite tests, compilation, and
`git diff --check`. The package root and all existing producer APIs remain
unchanged. Provider access, chain retrieval, incomplete-description resolution,
eligibility policy, generation, monitoring, and execution remain absent.

This file is a concise navigation map, not a complete specification or
history.
