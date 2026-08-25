# Last30Days Event Discovery Producer Evaluation

Date: 2026-08-25

Status: properly enabled controlled rerun completed with an empty validated
batch; material incremental value not demonstrated in the rerun window

## Purpose and authority boundary

This repository-external exercise evaluates `last30days-skill` as a third
Event Discovery producer after bounded Web Search and the Anthropic
`morning-note` baseline. It does not replace either producer.

The evaluated Skill is MIT-licensed `mvanhorn/last30days-skill` version 3.21.1,
pinned to upstream commit
`d05389d39b2ce09a13f71b01e68562f077c766df`. It is installed outside the
repository. Its native engagement, velocity, relevance, rank, recommendation,
content-worthiness, podcast-angle, X-article-angle, and prediction-market
semantics have no Hunter authority and are not retained in
`EventCandidate` or `EventCandidateBatch`.

Social and community records can support only the provisional statement that
a narrative deserves investigation. They cannot establish an authoritative
fact, exact event date, expected window, resolved underlying, impact path, or
Event Intelligence acceptance.

## Fixed-window adapter profile

Native `last30days --discover` rejects a historical `--as-of` because it sweeps
only current live listings. The bounded adapter therefore uses the Skill's
documented scripting interface with:

- a broad, frozen three-subquery research plan covering public-company events,
  emerging narratives, and second-order policy/supply-chain/technology links;
- a six-day native difference, which denotes seven inclusive calendar dates;
- versioned agent JSON schema 1.2;
- at most ten source-backed leads in neutral canonical order, without padding;
- no local corpus, market data, or repository write; and
- all native and credential-bearing configuration outside the repository.

Codex's bundled Python 3.12.13 satisfied the Skill runtime without changing
the project Python environment. A temporary external virtual environment added
only `yt-dlp` 2026.8.19 so the comparison did not omit keyless YouTube solely
because of the host PATH.

The adapter rules remain:

```text
last30days native agent JSON
-> require exact pinned schema and the six-day native difference that denotes
   the seven inclusive calendar dates
-> reject evidence outside the requested dates
-> discard rank, score, engagement, recommendation, and content angles
-> extract source-backed leads only
-> retain at most ten in neutral canonical order, without padding
-> construct existing EventCandidateBatch
-> explicit human selection of zero or one only when rows exist
```

No repository contract or public API changed.

## Preliminary run: inconclusive

The 2026-08-18 through 2026-08-24 run used no credentials and disabled browser
cookies. Hacker News and YouTube completed, but Reddit returned `auth-failed`
and X was not configured. Its empty export and zero-candidate batch are valid
mechanically, but they are not negative product evidence because the intended
narrative/attention coverage was incomplete.

The earlier wording that treated this run as demonstrating no material value
is superseded by this correction. It remains useful only as setup evidence.

## Properly enabled controlled rerun

The rerun used the new 2026-08-19 through 2026-08-25 inclusive window. The
external frozen plan retained these search controls:

| Label | Search query | Weight |
| --- | --- | --- |
| `company_events` | `US public company event regulation operations` | 1.0 |
| `emerging_narratives` | `company emerging narrative controversy disruption` | 0.8 |
| `second_order` | `business second order impact supply chain policy technology` | 0.7 |

The date rule, maximum result count, and Hunter adapter also remained
unchanged. The source arrays added X, which had been unavailable in the
preliminary run; Reddit's runtime backend changed as described below.

Runtime source enablement was repository-external:

- X used the Skill's browser-cookie path after explicit user consent; no cookie
  value was stored in repository state or emitted in the result;
- Reddit used the Skill's ScrapeCreators backend after an explicit GitHub
  device authorization, with the provider key stored only in the user's
  external `~/.config/last30days/.env`;
- YouTube used an external temporary `yt-dlp` environment and the configured
  provider fallback; and
- native artifacts remained under `/private/tmp`.

The run reported five of five core sources covered. Its versioned source
outcomes were:

| Source | Outcome |
| --- | --- |
| Hacker News | `ok` |
| YouTube | `ok` |
| Reddit | `ok` |
| X | `no-results` |
| Polymarket | `no-results` |
| keyless Web / grounding | `unreachable` |

`no-results` is valid source coverage, not an authentication failure. The Web
lane was not established by this run, so no Web silence is inferred; bounded
Web Search remains the separate existing baseline. The versioned export
contained no cluster or result. Hunter does not infer which internal filtering
stage caused the empty export. The observed output was:

```text
clusters = []
results = []
window_days = 6
```

The repository-external adapter constructed and validated:

```text
batch_id = last30days-2026-08-19--2026-08-25-v2
producer_id = last30days-bounded-adapter
candidate_count = 0
```

An empty batch is a valid existing contract result. It was not padded, retried
with a more favorable query, or converted into invented candidates.

## Controlled-comparison conclusion

| Dimension | Result |
| --- | --- |
| Human willingness to continue | Not measurable; no row existed to present |
| Novelty over Web Search | Not demonstrated |
| Second-order connection value | Not demonstrated |
| Source verifiability | Core coverage completed; Reddit, YouTube, and HN were `ok`, X and Polymarket validly returned no results; Web remained unreachable |
| Underlying mapping credibility | Not measurable |
| False-positive/speculative-link rate | No Hunter candidates emitted; internal filtered rows are not candidate evidence |
| Rejection reason | No lead was present in the producer's exported result for the frozen window |

No human `NONE` is attributed to this batch because no selectable row existed.
No candidate-to-submission translation, Event Intelligence assessment, market-
data call, Futu exercise, or Engine evidence work followed.

This result does not prove that attention-oriented discovery lacks value. It
does answer the bounded product question negatively for this properly enabled
window and frozen query policy: `last30days` surfaced no lead to present for
comparison with the prior bounded Web Search and `morning-note` batches.
`last30days` remains an experimental bounded producer, not a baseline or
preferred producer. A future rerun requires a separately justified coverage
change or a new comparison window; it must not optimize queries merely to
force a nonempty batch.
