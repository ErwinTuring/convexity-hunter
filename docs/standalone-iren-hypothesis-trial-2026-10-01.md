# Retained-source IREN hypothesis trial — 2026-10-01

Status: **EXECUTED ONCE / SEMANTIC_VERDICT_REJECTED**. Independent runner static
safety review passed; Main authorized the run after preregistration commit
`c0c851fa4a161e9177b6ff91dc0a2951e8630fa8`. This is a failed internal live
semantic stage, not live EI or independent product success. The external
prepared JSON remains the historical preparation artifact, not authorization.

## Actual result

- Producer and verifier each called/reserved once; both finished `stop`.
  Source calls zero; no retry, fallback or new attempt.
- Producer envelope structurally normalized: 11 claims, 1 hypothesis, 4 field
  bindings, 4 coverage entries. These are assertions, not semantic support.
- Producer audit finalized in memory. Runtime stopped at
  `SEMANTIC_VERDICT_REJECTED`, exit 1; exact rejection cause was not exposed.
  Do not infer invalid facts, absent events or bad source quality from this code.
- Receipt not validated; verified/rejected partitions and coverage outcomes
  unknown. Preparer calls zero; no submission, Builder result or EI assessment.
- Producer: request 48,483 bytes; 12.945 seconds; 15,031 prompt / 3,816
  completion / 18,847 total reported tokens.
- Verifier: request 76,313 bytes (within 80,000); 12.347 seconds; 21,449
  prompt / 3,571 completion / 25,020 total reported tokens.
- Total reported tokens 43,867; monetary cost unknown. No Tavily request or
  reservation was added. No raw model/verdict/audit payload was persisted.
- Exact sanitized stdout retained outside Git: 2,846 bytes; SHA-256
  `a57f798c935c5f29c10ae27c17ae8c690a6578cdbe4fe5d2d3a73b339f2d6580`.
  Role call/reservation counts are observed; a separate provider-transport
  invocation count was not exposed and remains unknown.

Next bounded work is offline failure-stage observability: distinguish verifier
wire parsing from semantic receipt construction without exposing payloads or
weakening either gate. The actual rejection cannot be reconstructed from this
aggregate, and must remain unknown. Do not replay this spent protocol or change
prompts/queries to manufacture acceptance. Independent MIC/currency proof and
production Host preparation remain separate unresolved dependencies.

## Frozen experiment boundary

- Production baseline: `68b43b43633bc84dfe47a5c36986434440b4b0f7`.
- Run ID: `iren-hypothesis-model-only-20261001-9e5d3a740cae4e7bbde396d23f2d98a1`.
- Input: research IREN's May 2026 GPU procurement and Microsoft-related
  financing as a possible structural change in project financing and operating
  obligations. Preserve four ordered questions: procurement, financing,
  distribution, temporal. Canonical input SHA-256:
  `c00fe346c8abf0f4d22a9b976f1062e616dd8fc57cbd5611c23e1874c7aa6fbb`.
- Consume only the already retained [SEC F1 filing](https://www.sec.gov/Archives/edgar/data/1878848/000114036126023427/ef20075181_8k.htm),
  9,423 UTF-8 bytes, body SHA-256
  `00ecc509846b657702081827db78a220b8ff51a9bacd19537339575e17ee6e29`.
  Retrieval: `2026-10-01T07:54:21.398098+00:00`; this is retained filing evidence,
  not proof of current draws, deployment or later amendments. Metadata remains
  `PENDING_BODY_REVIEW`; the narrow agreement-date anchor review does not
  establish completeness of the full source.
- Exactly one `deepseek-flash` producer and one separate verifier call at most;
  no source/Tavily request, refresh, retry or fallback. Exclusive attempt marker
  prevents reuse; allow only clean, docs-only descendants of the baseline.
- Explicit catalog runtime v0.2 with trusted Host preparer. Bind the first
  actually verified, relevant financing observed fact in neutral producer
  order as unchanged event description; no hardcoded model claim ID. Empty
  underlying binding map remains intentional: independent MIC and instrument
  currency proof is absent, not inferred from financing amounts.
- Host manually reviewed the agreement date `2026-05-29` from the exact source
  anchor at Unicode `[2603,2638)`, line 91, anchor SHA-256
  `9efb6189ebe4c80b6cf4a1672fe57503ae09b8181fc568f8cc59706e630f3fe8`.
  This independent, explicit Host case preparation supplies event chronology,
  not model dates or an impact window. It is not an autonomous date resolver.
- Unknown expected impact end stays absent. Only an actual source-backed,
  future, qualified milestone may support reassessment under existing closure
  rules; no preset deadline, caller-policy invention or maturity claim.
  Procurement not supported by F1 remains unresolved. Do not force a hypothesis,
  submission or ACCEPTED result; never replay the historical accepted case.

## Budgets and execution evidence

Catalog ceiling 32,768 bytes / 64 entries / 128 paragraphs; arrays 64; strings
8,000 bytes; source 20,000 bytes; original input 16,000 bytes; strict JSON and
model output 40,000 bytes; full model request 80,000 bytes; 6,000 output tokens;
45 seconds per call; JSON mode; thinking disabled. Actual verifier request
must fit before its one allowed call; exceedance stops without truncation.

Pure-local measurement: catalog 24,078 bytes / 48 entries; complete producer
request 48,483 bytes; verifier base 44,884 bytes. Synthetic verifier request
60,835 bytes is not a promise of live size. Offline fake-client validation and
12 guard / 8 preparer / 2 source / 2 attempt checks passed. Synthetic EI
INCOMPLETE is a fixture result, not live product evidence.

External runner: `/private/tmp/ch_iren_hypothesis_model_only_v0_2.py`, 35,575
bytes, SHA-256
`7c66fe34fefa4fd4133962687d882ff1060ada5a8fbb826c734d245c98ecf4a0`.
External preregistration JSON: 11,358 bytes, SHA-256
`54714d2feb18d5bb6092611dc50c1103ef26d785d67a88fbfa018e6c6a7ba94e`.
No credentials or raw source/model payloads are committed.

## Reporting boundary

Retain sanitized counts: validated envelope totals, receipt verified/rejected
partitions, coverage outcomes, description-selected flag/navigation index,
Builder diagnostic codes, EI status and issue-reason distribution; expose
unknown when failure precedes a stage. Keep source/model text, IDs, rationale,
exception messages and raw audit payloads out of output. Audit stays in memory.
No Core, market data, screening or trading call is part of this experiment.

This evaluates an internal live model-to-EI mechanism with explicit manual
Host preparation. It cannot establish an independently running product
Grounder or real source truth merely from two model judgments.
