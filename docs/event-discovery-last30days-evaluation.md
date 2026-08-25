# Last30Days Event Discovery Producer Evaluation

Date: 2026-08-25

Status: completed with an empty validated batch; material incremental value not
demonstrated in this window

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

The comparison uses the same 2026-08-18 through 2026-08-24 inclusive seven-day
window as the earlier producers. Native `last30days --discover` rejects a
historical `--as-of` because it sweeps only current live listings. The adapter
therefore used the Skill's documented scripting interface with:

- a broad, frozen three-subquery research plan covering public-company events,
  emerging narratives, and second-order policy/supply-chain/technology links;
- `--days=6 --as-of=2026-08-24`, because this Skill expresses the start as
  `as_of - days`; the six-day difference therefore covers the seven inclusive
  calendar dates from 2026-08-18 through 2026-08-24;
- versioned agent JSON schema 1.2;
- public Reddit, YouTube, Hacker News, Polymarket, and keyless Web lanes;
- browser-cookie reads explicitly disabled;
- no account, API key, social credential, local corpus, market data, or
  repository write; and
- all native artifacts written only under `/private/tmp`.

Codex's bundled Python 3.12.13 satisfied the Skill runtime without changing
the project Python environment. A temporary external virtual environment added
only `yt-dlp` 2026.8.19 so the comparison did not omit keyless YouTube solely
because of the host PATH.

The adapter rules are:

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

## Observed native result

The native run completed successfully and reported these per-source outcomes:

| Source | Outcome |
| --- | --- |
| Hacker News | `ok` |
| YouTube | `ok` |
| Reddit | `auth-failed` |
| Polymarket | `no-results` |
| keyless Web / grounding | `no-results` |
| X | not configured and not searched |

The retrieval layer encountered records internally, but the versioned native
export contained no cluster or result. Hunter does not infer which internal
filtering stage caused the empty export. The observed output was exactly:

```text
clusters = []
results = []
window_days = 6
```

The YouTube adapter logged that one supplemental query had no in-range videos
and temporarily retained older rows for its own processing. Because the final
versioned output contained zero results, no out-of-window row reached Hunter.
The bounded adapter nevertheless freezes an explicit date rejection so a
future nonempty run cannot rely on that native fallback.

The repository-external adapter constructed and validated:

```text
batch_id = last30days-2026-08-18--2026-08-24-v1
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
| Source verifiability | Partial; HN and YouTube completed, Reddit failed authentication, X was absent |
| Underlying mapping credibility | Not measurable |
| False-positive/speculative-link rate | No Hunter candidates emitted; internal filtered rows are not candidate evidence |
| Rejection reason | No lead was present in the producer's exported result for the frozen window |

No human `NONE` is attributed to this batch because no selectable row existed.
No candidate-to-submission translation, Event Intelligence assessment, market-
data call, Futu exercise, or Engine evidence work followed.

This result does not prove that attention-oriented discovery lacks value. It
does prove that the current no-credential, fixed-window `last30days` profile
did not add material Hunter discovery value beyond the two existing producers.
`last30days` remains an experimental bounded producer, not a baseline or
preferred producer. A future rerun requires a separately justified coverage
change or a new comparison window; it must not optimize queries merely to
force a nonempty batch.
