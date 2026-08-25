# SOC Event Discovery Real Exercise

Date: 2026-08-24

This is a sanitized product checkpoint. It records structured outputs and
human choices only. No credential, account identifier, raw provider payload,
or trading operation is retained.

## Bounded Web Search batch

The repository-external producer applied the frozen seven-calendar-day public-
information policy for 2026-08-18 through 2026-08-24 inclusive, deduplicated
the results, retained no more than ten source-backed items, and preserved a
neutral producer order. The resulting `EventCandidateBatch` validated with
nine candidates:

| Order | Candidate ID | Provisional underlying | Event |
| ---: | --- | --- | --- |
| 1 | `2026-08-18-bdx-fda-kit-alert` | BDX | FDA convenience-kit safety alert |
| 2 | `2026-08-18-amlx-lucidity-phase3` | AMLX | Phase 3 LUCIDITY topline result |
| 3 | `2026-08-19-rare-genglycos-approval` | RARE | FDA accelerated approval of Genglycos |
| 4 | `2026-08-20-bsx-enroute-class1-recall` | BSX | FDA Class I ENROUTE recall record |
| 5 | `2026-08-20-chtr-cox-liberty-close` | CHTR | Cox and Liberty transactions completed |
| 6 | `2026-08-21-gehc-portrait-software-alert` | GEHC | FDA Portrait software safety alert |
| 7 | `2026-08-21-howl-ambros-merger` | HOWL | Ambros merger and concurrent financing announced |
| 8 | `2026-08-21-soc-pipeline-court-ruling` | SOC | Pipeline-related federal court ruling disclosed |
| 9 | `2026-08-24-usar-serra-verde-spv` | USAR | Serra Verde SPV capitalization completed |

The user explicitly selected only
`2026-08-21-soc-pipeline-court-ruling`. Batch membership and presentation did
not establish importance, qualification, ranking, or a recommendation.

## Candidate-to-submission translation

Supplemental primary-source review corrected the candidate's initially one-
sided DOJ framing. The retained submission represented the August 19 order as
mixed evidence: the court found a violation and imposed a USD 1.449 million
penalty, declined to order shutdown, reached a federal-preemption result, and
left appeals pending. An issuer filing supplied a September 28 related hearing
date.

The caller explicitly constructed:

- event date: 2026-08-19;
- expected window: 2026-08-19 through 2026-09-28 inclusive;
- window methodology: order date through the next source-backed scheduled
  related hearing, not a litigation-resolution or market-impact forecast;
- underlying: `SOC`, `XNYS`, equity, USD;
- distribution mode: `BIDIRECTIONAL_EXPANSION`.

Translation bound the selected candidate, supplemental sources, and exact
caller-built submission. It did not invent missing fields or modify the
submission to make it pass. Existing Event Intelligence assessment returned
`ACCEPTED` with no issues.

## Browser-to-Direct-Entry result

At the 2026-08-24 evaluation date, the hypothesis passed the temporal-
applicability gate. The derived expiration interval was 2026-10-28 through
2027-01-21. Futu returned one eligible provider-monthly expiration,
2027-01-15, with 29 same-strike Call/Put pairs.

The user explicitly selected the neutral median pair:

- Call: `US.SOC270115C19000`;
- Put: `US.SOC270115P19000`;
- expiration: 2027-01-15;
- strike: 19;
- quantity: one contract per leg;
- assumed portfolio value: USD 10,000;
- expected holding period: 35 calendar days.

Both exact Futu leg verifications, the Browser-selection bridge, and the Direct
Entry exact-contract gate passed without contract substitution. Provider
multiplier 100 was retained for each leg. Both provider-neutral references
remained `INCOMPLETE`, and research readiness remained absent.

Candidate Assembly and screening therefore returned `DATA_INSUFFICIENT` with
the six preserved reasons:

- `missing_costs`;
- `missing_liquidity`;
- `missing_volatility_environment`;
- `missing_structure_expiration_tail_slice`;
- `missing_target_move_scenario`;
- `missing_volatility_crush_scenario`.

No position-management plan was created. The Chinese report was 3,519
characters with SHA-256
`114f1ae120cbb2da48dc92c92bbfeb71eb6f63b97de3f6316a8fb42ff4959326`.
No BBO, history, account, or trading call was made, and no raw provider payload
was persisted.

## Human and product feedback

The observable human feedback is the explicit SOC selection and the decision
to continue it through a real listed structure. It is not evidence that any
unselected event was unimportant.

The product interpretation is that SOC was useful because the user had not
pre-specified it, it affected a core operating asset, primary legal and issuer
sources exposed a genuinely mixed outcome, appeals remained open, a later
source-backed procedural milestone bounded the expected window, one public-
company mapping was credible, and real listed options existed.

The remaining eight items were not selected in this exercise. The user did not
supply item-by-item rejection reasons. Product-level observations, not quoted
human judgments, are:

- BDX, BSX, and GEHC had authoritative safety evidence, but the reviewed
  sources did not establish scope or financial materiality and some discovery
  dates reflected later posting or correction activity;
- AMLX and RARE were substantial biotechnology events, but were familiar
  first-order issuer/regulatory catalysts and offered less mixed, second-order
  legal and operational structure than SOC in this batch;
- CHTR and HOWL were first-order corporate transactions with unresolved or
  broad integration and closing windows; and
- USAR remained conditional on a later acquisition close and lacked a bounded
  expected-impact window.

This one exercise demonstrates a usable Hunter loop; it does not establish
repeatability by itself.
