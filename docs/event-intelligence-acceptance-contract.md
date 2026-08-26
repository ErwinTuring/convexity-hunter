# Event Intelligence Acceptance Contract v0.1

> Historical v0.1 contract. The implemented runtime contract is the
> separately frozen
> [Event Intelligence Temporal Semantics Contract v0.2](event-intelligence-temporal-semantics-v0.2-contract.md)
> and its acceptance version is `event-intelligence-acceptance-v0.2`. Existing
> v0.1 results remain historical records and are not runtime inputs.

## Purpose

This contract defines the smallest provider-neutral and Skill-neutral boundary
for accepting an auditable event-to-underlying hypothesis. Acceptance means
only that the hypothesis is sufficiently explicit to enter later discovery
work. It does not establish option eligibility, contract existence, pricing,
cheapness, probability, ranking, or a trade recommendation.

The implementation is `convexity_hunter.event_intelligence`. Its public names
are module-local; the package root remains unchanged.

## Records

`EventSourceReference` retains a stable `source_id`, optional locator and
title, and optional aware publication time. A missing locator is incomplete,
not malformed. A supplied blank value or naive datetime is malformed.

`EventStatement` is either `OBSERVED_FACT` or `INTERPRETATION`. Facts cite
structured source IDs and cannot depend on other statements. Interpretations
may cite sources directly or depend transitively on source-backed facts.
Statement IDs, source IDs, and dependency IDs are canonicalized and retained;
the dependency graph must be acyclic.

`MethodologizedDateRange` contains optional `start_date`, `end_date`, and
methodology. Its dates are inclusive. Partial ranges are structurally valid
and assess as incomplete; supplied datetimes or reversed complete boundaries
are malformed.

`DistributionChangeMode` is closed to:

- `EXTREME_TAIL_UP`;
- `EXTREME_TAIL_DOWN`;
- `EVENT_DIRECTIONAL_UP`;
- `EVENT_DIRECTIONAL_DOWN`; and
- `BIDIRECTIONAL_EXPANSION`.

`EventUnderlyingHypothesis` retains a stable ID, optional provider-neutral
`UnderlyingKey`, impact path, distribution mode, separate distribution
hypothesis text, expected window, supporting and contradicting statement IDs,
contradiction review, uncertainties, and falsification conditions. Supporting
and contradicting IDs must be disjoint. Acceptance requires supporting closure
to contain both a source-backed observed fact and an explicit interpretation.
An empty contradiction set is acceptable only when `contradiction_review`
records that the review occurred and found none.

`EventIntelligenceSubmission` retains a stable submission ID, optional event
ID, producer ID/version, aware observation time, event description, inclusive
event date range, structured sources, statements, and one or more hypotheses.
The producer may be a Skill, adapter, deterministic local process, or another
bounded producer. No LLM identity is assumed. Sources, statements, and
hypotheses are canonicalized by their stable IDs. Duplicate IDs, dangling
references, cycles, and a source publication time later than the submission
observation time are malformed. Exact record types are intrinsically
reconstructed at the public boundary so subclasses and constructor-bypassed
nested records cannot authorize acceptance.

`EventIntelligenceAcceptanceResult` retains the exact submitted object,
status, subject-bound issues, and fixed assessment version
`event-intelligence-acceptance-v0.1`. Issues are ordered by closed issue-code
declaration order and then subject ID. `issue_codes` is the unique ordered
projection. Status is `ACCEPTED` exactly when no issues exist and `INCOMPLETE`
otherwise.

## Malformed versus incomplete

Constructors or the assessor raise controlled `TypeError` or `ValueError` for
malformed structure, including wrong types, blank supplied values, duplicate
IDs, dangling references, dependency cycles, observed-fact dependencies,
support/contradiction overlap, naive supplied datetimes, reversed supplied
ranges, chronology contradictions, and an empty hypothesis collection.

Missing semantic evidence remains representable and produces deterministic
`INCOMPLETE` issues. The closed issue taxonomy covers missing event and
producer identity, observation and event-time semantics, structured sources
and locators, statements and source closure, underlying identity, impact and
distribution hypotheses, expected window, supporting fact/interpretation,
contradiction review, uncertainty, and falsification conditions. No missing
field is inferred from prose or external state.

## Purity and ordering

`assess_event_intelligence_submission` performs no web, provider, Skill, LLM,
market-data, ranking, candidate, report, or persistence operation. It is
deterministic, caller-order invariant, and does not mutate the submission.
Canonical tuple ordering is lexicographic by normalized ID or text; issue
ordering is semantic enum order followed by subject ID. Statement graph
validation and closure traversal are iterative and do not depend on Python's
recursion limit.

## Explicit non-goals

This work unit does not implement source discovery, SEC or GDELT clients,
third-party Skill installation, prompt orchestration, event monitoring,
security ranking, option-chain retrieval, structure generation, screening,
report integration, or a generic plugin/provider framework. A future adapter
may translate a bounded producer-native result into this contract, but the
adapter cannot weaken its source, identity, chronology, or uncertainty rules.
