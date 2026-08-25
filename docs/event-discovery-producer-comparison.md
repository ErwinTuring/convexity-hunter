# Event Discovery Producer Comparison

Status: completed with explicit human selection `NONE`

## Purpose and frozen boundaries

This controlled exercise compares two bounded producers over the same
2026-08-18 through 2026-08-24 inclusive window and U.S.-listed equity/ETF
scope:

1. the existing bounded Web Search producer; and
2. one adapted external Skill producer.

Each producer emits at most ten records into the existing `EventCandidate` and
`EventCandidateBatch` contract. Candidate visibility is provisional. Neither
producer ranks, scores, recommends, automatically promotes, invokes market
data, or changes Event Intelligence acceptance. Presentation order is neutral
navigation order only.

## External Skill integration

The selected external Skill is Anthropic's `morning-note` Skill from the
Apache-2.0 `anthropics/financial-services` repository, pinned for this exercise
to upstream commit `e5edf36b69fa2fcd7ad6273ca8b4fb1e4e9376ad`.

The Skill is mature enough to investigate because it belongs to an established
open-source financial-services Skill collection and provides a concrete daily
event taxonomy spanning earnings and guidance, M&A, management changes,
product developments, regulatory decisions, and macro policy. It is installed
as a user-level Codex Skill outside this repository; the repository contains
no copied Skill runtime or user configuration.

Only the event-taxonomy and source-scanning portion is adapted. The bounded
profile explicitly excludes the Skill's Top Call, analyst actions, ratings,
price targets, price movement, market positioning, trade ideas,
recommendations, prioritization, and scoring. This prevents the external Skill
from acquiring authority absent from the existing Event Discovery contract.

The adapter is repository-external and constructs ordinary validated
`EventCandidate` records. Its producer identity is
`anthropic-morning-note-adapted`; its pinned profile version is
`financial-services-e5edf36-morning-note-bounded-v0.1`. No new repository API,
orchestration framework, or acceptance path is introduced.

## Controlled batches

The Web Search batch produced nine records. Its completed SOC exercise is
recorded separately in
[`event-discovery-soc-real-exercise.md`](event-discovery-soc-real-exercise.md).

The adapted Skill batch also validated with nine records in date then
candidate-ID order:

| Order | Candidate ID | Provisional underlying | Event | Primary source |
| ---: | --- | --- | --- | --- |
| 1 | `2026-08-18-bdx-fda-kit-alert` | BDX | FDA convenience-kit safety alert | FDA |
| 2 | `2026-08-18-fda-genai-device-rfc` | none | FDA request for feedback on generative-AI medical devices | FDA |
| 3 | `2026-08-19-fomc-minutes` | none | July FOMC minutes released | Federal Reserve |
| 4 | `2026-08-19-panw-frontier-ai-defense` | PANW | Frontier AI Critical Defense Program announced | Palo Alto Networks |
| 5 | `2026-08-19-rare-genglycos-approval` | RARE | Genglycos accelerated approval | FDA and Ultragenyx |
| 6 | `2026-08-19-soc-pipeline-court-order` | SOC | Mixed pipeline-related federal court order disclosed | SEC-filed order and issuer 8-K |
| 7 | `2026-08-19-tgt-q2-guidance` | TGT | Q2 results and updated guidance | Target |
| 8 | `2026-08-20-chtr-cox-liberty-close` | CHTR | Cox and Liberty transactions completed | Charter |
| 9 | `2026-08-21-howl-ambros-merger` | HOWL | Ambros merger and financing announced | Werewolf Therapeutics |

All nine Skill records retain source-backed exact event dates and primary
official sources. All expected windows remain absent. Seven contain a
provisional issuer mapping; the FDA policy request and FOMC minutes deliberately
do not infer one.

## Mechanical comparison

Five semantic events overlap: BDX, RARE, CHTR, HOWL, and SOC.

Web Search uniquely retained AMLX Phase 3 results, the BSX recall, the GEHC
safety alert, and the USAR financing. The adapted Skill uniquely retained the
FDA generative-AI policy request, FOMC minutes, the PANW program, and Target's
Q2 guidance.

The Skill profile therefore changed category coverage, but different output is
not yet material product value. Preliminary, non-human observations are:

- source quality is high for both batches; every Skill record uses primary
  official evidence;
- the FDA policy and FOMC records increase thematic breadth but lack a
  source-backed exact underlying mapping at candidate time;
- PANW and TGT map directly but remain first-order issuer events unless later
  evidence supports a more useful connection;
- no unique Skill record currently supplies a source-backed second-order
  underlying connection; and
- the Skill missed four source-backed events found by bounded Web Search.

## Human result

The user explicitly selected `NONE`. This is a valid Hunter product result,
not a failure to be repaired. No candidate-to-submission translation, Event
Intelligence assessment, market-data call, or downstream Futu exercise was
performed for the Skill batch.

The recorded human evaluation is:

- usefulness: no clear improvement;
- novelty: a small improvement, primarily from the FDA generative-AI medical-
  device request for feedback;
- second-order connections: some potential, but no research-ready mapping;
- source quality: high and comparable to bounded Web Search; and
- underlying mapping: no better overall than bounded Web Search.

The user found the FOMC minutes and Target earnings/guidance to be visible
traditional catalysts, the PANW distribution-change path comparatively weak,
and the FDA generative-AI policy item novel but too open-ended in its
underlying mapping to warrant formal Event Intelligence review. The five-event
overlap and those limitations mean that the adapted Skill did not demonstrate
material incremental discovery value in this controlled window.

`morning-note` remains useful as a traditional institutional-event discovery
baseline. It is not promoted to the preferred producer and does not replace
bounded Web Search. The next producer evaluation should investigate a mature
narrative/attention discovery Skill rather than optimize this adapter. Any
such producer must still emit the unchanged provisional records, preserve
neutral order and explicit `NONE`, and stop before translation unless the user
selects one candidate.
