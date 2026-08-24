# Event Discovery / Event Intake Contract v0.1

## Purpose

This Tier-A contract defines the smallest provider-neutral boundary between a
bounded external discovery producer and the existing Event Intelligence
acceptance boundary. It allows a producer to surface at most ten provisional,
source-backed event candidates, lets a human explicitly select zero or one,
and binds one selected candidate to one explicitly constructed
`EventIntelligenceSubmission`.

An `EventCandidate` is neither an accepted Event Intelligence hypothesis nor a
`CandidateResearchRecord`. Discovery visibility means only that the producer
found the event sufficiently relevant to include under its declared bounded
policy. It establishes no factual completeness, importance, opportunity,
pricing, recommendation, or downstream eligibility.

The implementation is `convexity_hunter.event_discovery`. Its public names are
module-local and are not re-exported from the package root.

## Public API

The direct module exports exactly:

```text
EventCandidate
EventCandidateBatch
EventCandidateSelection
EventCandidateTranslation
select_event_candidate
translate_event_candidate_selection
```

## Candidate record

`EventCandidate` retains exactly:

```text
candidate_id
deduplication_key
event_description
observed_at
event_date_range
expected_window
sources
authoritative_source_ids
provisional_underlying_symbols
distribution_change_rationale
contradiction_review
uncertainties
```

The candidate ID and producer-supplied deduplication key are stable nonempty
strings. `observed_at` is an aware UTC-normalized datetime. Event dates and the
expected window are optional `MethodologizedDateRange` records and remain
missing when the producer lacks evidence. The constructor derives or extends
no date.

Every candidate has at least one exact `EventSourceReference` with a locator.
`authoritative_source_ids` is an optional subset identifying the sources the
producer classifies as authoritative; remaining sources are supporting or
discovery sources. Source publication times cannot follow candidate
observation time.

Potentially affected underlyings remain provisional trimmed symbol strings.
The candidate layer constructs no `UnderlyingKey`, listing identity, security
type, currency, exact impact mapping, or accepted hypothesis. The distribution
rationale is an explicit provisional interpretation, not a source fact.
Contradiction review and at least one uncertainty are required so discovery
does not present false certainty.

## Bounded batch and ordering

`EventCandidateBatch` retains exactly:

```text
batch_id
producer_id
producer_version
observed_at
discovery_policy
candidates
```

It preserves candidate object identity and exact caller presentation order.
The order has navigation semantics only. It is not an opportunity, importance,
attractiveness, market-impact, or recommendation ranking.

The batch permits zero through ten candidates. A discovery producer should aim
to retain five through ten source-backed candidates, but it must return fewer
or zero rather than pad the batch. More than ten candidates, duplicate
candidate IDs, duplicate deduplication keys, and candidate observation times
after batch observation time fail closed.

The first bounded repository-external policy is:

```text
recent public information over an explicit seven-calendar-day window
-> U.S.-listed equity or ETF events with plausible distribution-shift relevance
-> prefer regulator, government, SEC, exchange, and issuer primary sources
-> permit reputable reporting as discovery/supporting evidence
-> exclude unsupported social narratives, analyst opinion alone,
   and price movement alone
-> deduplicate the same event/entity/date
-> retain no more than ten without padding
-> preserve producer presentation order without score semantics
```

This policy identifies the first exercise producer; it is not embedded in the
provider-neutral records and creates no generic news platform.

## Explicit human selection

`EventCandidateSelection` retains one exact batch and either no selected
candidate or one candidate retained by identity in that batch.
`select_event_candidate` accepts an explicit candidate ID or `None`; it has no
default and performs no ranking. An equal copy or candidate outside the exact
batch cannot authorize selection.

No selection is a valid terminal human result. Translation requires one
selection and therefore rejects the zero-selection result.

## Candidate-to-submission translation

`EventCandidateTranslation` retains exactly:

```text
selection
submission
supplemental_sources
```

`translate_event_candidate_selection` receives an already explicit exact
`EventIntelligenceSubmission`. It does not create, infer, repair, retry, or
assess the submission. It binds provenance only:

- every candidate source must appear in the submission by exact record
  identity;
- every supplemental source must have a locator and appear by exact record
  identity;
- candidate and supplemental source IDs must be disjoint;
- the submission source set must equal their exact union, with no missing or
  unexplained source; and
- a supplied submission observation time cannot precede candidate observation.

Supplemental research may support explicit facts, dates, underlying identity,
or expected-window methodology. If it does not establish a field, that field
remains missing. Translation must never invent a plausible value or optimize a
submission to pass acceptance. Free text in a submission remains subject to
the existing fact-versus-interpretation, source-closure, contradiction,
uncertainty, and falsification requirements.

After translation, a separate caller may invoke the existing
`assess_event_intelligence_submission`. `INCOMPLETE` is an ordinary valid
outcome. Translation never calls the assessor or automatically promotes a
candidate into Discovery Entry.

## Failure and trust boundary

Exact types and intrinsic reconstruction reject subclasses, malformed or
noncanonical constructor-bypassed records, malformed nested dates or sources,
duplicate identities, source chronology contradictions, unexplained
submission sources, equal-but-not-identical source copies, and selection
copies not retained by the batch. A same-type object whose complete exact field
state is canonical and value-identical to constructor output is intentionally
validated by reconstruction; Python constructor history is not treated as
economic or source provenance and no hidden global instance registry is added.
Inputs are immutable and no external state is read.

## Non-goals

This unit adds no external search adapter, news platform, Skill, LLM call,
multi-agent orchestration, knowledge graph, score, automatic ranking,
automatic promotion, Event Intelligence acceptance change, source-content
storage, persistence, monitoring, market data, quote, ATM/Delta logic,
structure generation, Candidate Assembly, recommendation, or trading. It does
not change or attempt to complete any existing Engine `missing_*` evidence.
