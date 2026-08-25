# Hunter Discovery Policy v0.1

## Status and purpose

This policy freezes the smallest bounded interpretation policy for the current
Event Discovery MVP. It tests whether public Web Search plus explicit
distribution-shift reasoning can repeatedly surface an event or connection a
human did not pre-specify and genuinely wants to investigate.

Bounded Web Search is the only active producer under this policy. Further
Skill tuning and the six existing Engine `missing_*` work items remain frozen.
An `EventCandidate` remains provisional and has no recommendation, importance,
opportunity, or downstream-eligibility meaning.

## Bounded producer policy

Each run declares one inclusive seven-calendar-day source-publication window
and applies this sequence:

```text
public information published within the declared window
-> source qualification
-> one primary discovery lane per retained lead
-> explicit separation of source facts and Hunter interpretation
-> provisional U.S.-listed equity/ETF mapping when support exists
-> same-event/entity/date deduplication
-> no more than ten candidates, with no padding
-> neutral deterministic presentation order
-> explicit human selection of zero or one
```

The event itself may occur outside the source-publication window when a source
inside the window explicitly reports or announces it. Event dates, expected
windows, underlyings, and causal links remain absent when the sources do not
support them. The producer does not silently extend a date or window.

The batch `discovery_policy` identifies this policy, its exact inclusive
window, and its neutral ordering rule:

```text
hunter-discovery-policy-v0.1;
window_start=YYYY-MM-DD;
window_end=YYYY-MM-DD;
order=earliest-source-publication-asc,candidate-id-asc
```

The physical string is stored on one line. Candidates are ordered by the
earliest publication date or timestamp among their retained sources, ascending,
then by `candidate_id` lexical order. This is navigation order only. It is not
a score or ranking.

## Discovery lanes

Every retained candidate has exactly one primary lane:

### `EXPLICIT_CATALYST`

A source-backed regulatory, litigation, clinical, transaction, policy,
operational-disruption, or similarly discrete development with a plausible
path to changing an identified underlying's outcome distribution.

### `NARRATIVE_BELIEF_SHIFT`

Source-backed evidence that an industry, technology, business model, policy,
or market narrative may be gaining, losing, or splitting in credibility. A
price move, analyst opinion, or attention signal alone is insufficient. The
candidate must identify the observed evidence and keep the belief-shift claim
provisional.

### `SECOND_ORDER_TRANSMISSION`

A source-backed event directly affects entity or sector A, while Hunter
identifies an explicit provisional path to B or C through supply chain,
regulation, dependency, substitution, capital flows, competitive structure,
or another named mechanism. Every factual hop must be source-backed. The
transmission conclusion remains Hunter interpretation and may not be presented
as source fact.

Overlap does not create multiple lanes. The producer chooses the lane that
explains why Hunter surfaced the item and may disclose secondary characteristics
inside the provisional interpretation.

## Representation without a contract change

The existing `EventCandidate` schema is sufficient. A new lane field is not
added because lane assignment is producer-policy metadata, not accepted Event
Intelligence evidence.

- `event_description` contains only source facts and attribution.
- `distribution_change_rationale` uses this exact two-line grammar:

```text
DISCOVERY_LANE=<EXPLICIT_CATALYST|NARRATIVE_BELIEF_SHIFT|SECOND_ORDER_TRANSMISSION>
HUNTER_INTERPRETATION=<nonempty provisional impact or transmission rationale>
```

- `sources` retain exact public locators and publication timing when available.
- `authoritative_source_ids` identify only sources qualified as authoritative;
  other retained sources remain discovery or supporting evidence.
- `provisional_underlying_symbols` contains only supportable U.S.-listed equity
  or ETF mappings and may be empty.
- `contradiction_review` identifies checked counterevidence or states the
  bounded review performed.
- `uncertainties` retains at least one concrete reason the interpretation may
  fail or remain incomplete.

A producer-side validator must reject a candidate whose rationale does not
match the grammar, has more than one lane, lacks a public source, falls outside
the declared source-publication window, duplicates the same event/entity/date,
or exceeds the batch limit. These checks do not alter the provider-neutral
constructor contract.

## Source and interpretation boundary

Regulators, government bodies, courts, exchanges, SEC filings, and issuer
primary materials are preferred. Reputable reporting may discover or support
a candidate. Social, community, and attention evidence may support discovery
only; it cannot make a fact authoritative.

Hunter interpretation must be visibly separate from source facts. The policy
does not invent or repair event dates, expected windows, underlying identity,
or causal links. Candidate-to-submission translation remains a provenance
binding and source-supported research step; it cannot manufacture fields merely
to pass Event Intelligence acceptance.

## Human evaluation protocol

Each real batch stops before translation. The human explicitly selects one
candidate ID or `NONE` and records:

- willingness to continue researching;
- whether the event itself was new;
- whether the event-to-underlying connection was new;
- whether the impact or transmission path was credible or too speculative;
- rejection reasons; and
- the selected candidate's discovery lane, if any.

Only an explicit selection may proceed to supplemental verification and the
existing Event Intelligence acceptance boundary. Futu and Direct Entry do not
run by default.

## Validation outcome

Three sequential, previously unused seven-day windows produced 9, 6, and 8
validated candidates. The human selected one item from every batch, reported
that every selected event and connection was new, and rated all three impact
paths mixed. The useful lanes were one `SECOND_ORDER_TRANSMISSION` and two
`NARRATIVE_BELIEF_SHIFT`; direct first-order catalysts dominated the recorded
rejection reasons.

This is bounded positive repeatability evidence that the policy's
distribution-shift interpretation adds discovery value beyond merely listing
public events. It is not a claim of completeness, causal truth, investment
attractiveness, or recommendation quality. All three selected translations
remained honestly `INCOMPLETE` because no authoritative source supplied an
exact expected-window end date. The full sanitized evidence is in
[`hunter-discovery-policy-v0.1-validation.md`](hunter-discovery-policy-v0.1-validation.md).

## Non-goals

This policy adds no scoring, attractiveness ranking, recommendation,
auto-promotion, market-data feedback, automatic structure generation, generic
news platform, knowledge graph, multi-agent orchestration, or Engine evidence
work. It does not change `EventCandidate`, `EventCandidateBatch`, Event
Intelligence, Browser, Direct Entry, or research evidence contracts.
