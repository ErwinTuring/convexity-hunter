# Event Intelligence Temporal Semantics Contract v0.2

## Status

This Tier-A contract is frozen as the target for a later BUILD. It is not yet
implemented. The current runtime remains Event Intelligence acceptance v0.1
and Option-Chain Discovery Request v0.2.

This contract separates three temporal meanings that current runtime behavior
derives from one `expected_window.end_date`:

1. expected market or distribution impact;
2. hypothesis reassessment and research validity; and
3. the downstream option-maturity anchor.

It does not predict how long a narrative will persist, weaken fail-closed
behavior, or make Event Intelligence acceptance equivalent to option-discovery
readiness.

## Exact temporal meanings

`expected_window` continues to mean only the inclusive expected market or
distribution-impact window. A complete window contains exact `start_date`,
`end_date`, and methodology. Its end date is an impact claim, not merely a
workflow deadline.

`reassessment` is research-governance state. Its `reassessment_by` date means:

> this hypothesis must be freshly reassessed no later than this date before it
> may continue to authorize current research.

It is not a predicted impact end, event end, option holding period, or option
maturity recommendation. It must never be rendered as any of those meanings.

An option-maturity anchor is the authoritative date used by the downstream
policy that requires expiration at least 30 calendar days after the bounded
impact window. In v0.2, only a complete `expected_window.end_date` supplies
that anchor. `reassessment_by` never does.

## Proposed public contract shape

The later BUILD adds these module-local exact types to
`convexity_hunter.event_intelligence`:

```python
class ReassessmentBasisKind(str, Enum):
    SOURCE_BACKED_MILESTONE = "source_backed_milestone"
    CALLER_RESEARCH_POLICY_ASSUMPTION = "caller_research_policy_assumption"


@dataclass(frozen=True)
class HypothesisReassessment:
    reassessment_by: datetime.date
    methodology: str
    basis_kind: ReassessmentBasisKind
    basis_statement_ids: Tuple[str, ...]
```

The direct-module `__all__` inserts `ReassessmentBasisKind` and
`HypothesisReassessment`, in that order, immediately after
`DistributionChangeMode`. Neither name is re-exported from the package root.

`EventUnderlyingHypothesis` retains the existing `expected_window` field and
inserts `reassessment` immediately after it. Its exact field order becomes:

```python
hypothesis_id
underlying_key
impact_path
distribution_mode
distribution_hypothesis
expected_window
reassessment
supporting_statement_ids
contradicting_statement_ids
contradiction_review
uncertainties
falsification_conditions
```

The exact annotation of the new hypothesis field is
`Optional[HypothesisReassessment]`.

`reassessment` is the only optional layer. When present, every nested field is
required and non-optional. `reassessment_by` requires exact `datetime.date`
rather than `datetime.datetime`; methodology is a nonempty normalized string;
`basis_kind` requires the exact closed enum; and `basis_statement_ids` is a
nonempty canonical tuple of exact statement IDs. Partial reassessment state is
not representable. Malformed nested values raise controlled `TypeError` or
`ValueError` rather than producing an incomplete record.

No field is added to `EventCandidate`. Candidate-to-submission translation
continues to receive an explicitly constructed submission and neither derives
nor repairs temporal semantics.

## Provenance and basis rules

Every `basis_statement_id` must resolve inside the same exact submission. The
reassessment record does not create a new source authority or bypass the
existing fact-versus-interpretation boundary. Basis validation is closed by
`basis_kind`; arbitrary methodology prose is not sufficient.

For `SOURCE_BACKED_MILESTONE`:

- `basis_statement_ids` contains exactly one direct `OBSERVED_FACT` statement;
- that statement has at least one exact source ID, is also retained in the
  hypothesis supporting closure, and its text contains the exact
  `reassessment_by.isoformat()` date;
- methodology is exactly
  `source-backed-milestone:<statement-id>:<YYYY-MM-DD>`, where both structured
  values equal the retained statement ID and `reassessment_by`; and
- an approximate year, lease term, transaction completion date, or vague
  phrase such as "over time" is insufficient.

These rules deterministically bind the reassessment record to the submission's
exact source-backed date assertion. They do not independently fetch or parse
the external source; the observed-fact author remains responsible for the
truthful source representation under the existing source contract.

For `CALLER_RESEARCH_POLICY_ASSUMPTION`:

- the basis-statement closure contains both a source-backed observed fact and
  an explicit interpretation already relevant to the hypothesis;
- methodology is exactly
  `caller-research-policy-assumption:<YYYY-MM-DD>:<nonempty-rationale>`, with
  the structured date equal to `reassessment_by`;
- linked statements provide the factual or interpretive context being kept
  under review, not evidence that the market impact ends on that date;
- the date must not be presented as source-stated unless a source actually
  states it; and
- no adapter, LLM, producer, or default policy may manufacture 30-, 60-, or
  90-day horizons merely to obtain acceptance.

The submission's producer identity, observation time, exact reassessment
record, statement graph, source graph, basis-kind-specific grammar, and exact
date equality together preserve provenance. The assessor validates this
structure; it does not claim that the caller's governance rationale is an
authoritative market fact. Producer governance and independent review must
reject a caller rationale that disguises a forecast or generic default as a
research rule.

## Completeness and acceptance

The v0.2 temporal acceptance matrix is:

| `expected_window` | `reassessment` | Temporal acceptance |
| --- | --- | --- |
| complete | absent | Complete bounded-event semantics |
| complete | complete | Complete; both independent boundaries are retained |
| absent | complete | Complete structural-only semantics |
| absent | absent | `INCOMPLETE / missing_temporal_applicability` |
| partial | any value | `INCOMPLETE / incomplete_expected_window` |

A partial `expected_window` never becomes complete merely because a
reassessment exists. A structural-only submission omits `expected_window`
rather than supplying a guessed end date. Known event dates remain in
`event_date_range`; they are not silently promoted into an impact window.

Event Intelligence v0.2 acceptance means only that the hypothesis is
auditable, has a valid current-research boundary, and satisfies all unchanged
identity, source, impact-path, distribution, contradiction, uncertainty, and
falsification requirements. It does not establish an impact end, maturity
anchor, option eligibility, pricing, or research readiness.

The closed issue taxonomy adds
`MISSING_TEMPORAL_APPLICABILITY = "missing_temporal_applicability"`.
`INCOMPLETE_EXPECTED_WINDOW` remains unchanged for an explicitly supplied but
partial impact window. There is no `incomplete_reassessment` issue because a
present `HypothesisReassessment` is atomic and complete by construction.
The new enum member is declared immediately after
`INCOMPLETE_EXPECTED_WINDOW`; its issue is bound to the exact hypothesis ID.
Issue ordering otherwise remains declaration order and then subject ID.

## Chronology and stale-hypothesis behavior

When submission `observed_at` is present, `reassessment_by` must be on or after
its UTC calendar date. A reassessment deadline before observation is a
chronology contradiction and fails controlled validation.

The inclusive applicability boundary is:

```text
complete expected_window only
    -> expected_window.end_date

complete reassessment only
    -> reassessment.reassessment_by

both complete
    -> min(expected_window.end_date, reassessment.reassessment_by)
```

The boundary day remains applicable. `evaluation_date` later than the boundary
fails closed before option-discovery arithmetic. Taking the earlier boundary
ensures that reassessment never extends a bounded impact window.

Expiry requires a freshly constructed submission, new v0.2 assessment, and new
handoff. The replacement temporal evidence depends on the expired basis:

- an expected-window-only hypothesis requires a newly supported complete
  expected impact window; it does not require a reassessment record;
- a reassessment-only hypothesis requires a newly explicit complete
  reassessment record; and
- when both exist, expiry at the earlier boundary cannot be cured by extending
  only the later boundary. An expired expected impact window requires new
  impact-window evidence and can never be extended by reassessment.

No record is mutated, rolled forward, copied with a later date, or
automatically extended. The previous accepted result remains historical
evidence of its original boundary.

## Option-discovery readiness

Event Intelligence acceptance and Option Discovery readiness are independent.
A currently applicable structural-only hypothesis may be:

```text
Event Intelligence: ACCEPTED
Temporal applicability: CURRENT
Option Discovery: NOT READY
Reason: missing_authoritative_maturity_anchor
```

The later Option-Chain Discovery Request contract must freeze the exact stable
failure text:

```text
missing_authoritative_maturity_anchor
```

The smallest implementation is a controlled `ValueError` with that exact
message and no request object. It does not add a generic readiness framework.

Validation order is deterministic:

1. validate the exact accepted handoff and hypothesis;
2. derive the inclusive applicability boundary above;
3. if expired, fail as stale and require a fresh submission under the basis-
   specific renewal rules above;
4. require a complete `expected_window.end_date` as the maturity anchor;
5. if absent, fail with `missing_authoritative_maturity_anchor`;
6. only then derive the unchanged 30--150 DTE and
   `expected_window.end_date + 30 days` interval.

No `reassessment_by`, event date, publication date, observation date,
expected holding period, provider expiration, or user-selected contract may
substitute for the missing maturity anchor.

## Existing bounded-event compatibility

Existing bounded submissions migrate as:

```text
expected_window = existing complete value
reassessment = None
```

Their acceptance, inclusive stale boundary, minimum expiration formula,
maximum 150-DTE boundary, Futu retrieval, Browser filtering, and explicit human
selection behavior remain unchanged.

The later Event Intelligence implementation version becomes
`event-intelligence-acceptance-v0.2`. The BUILD is one atomic cutover:

- `event_intelligence._ASSESSMENT_VERSION` and
  `discovery_entry._ACCEPTANCE_VERSION` both become that exact value in the
  same commit;
- no runtime dual-version acceptance or fallback is permitted;
- intrinsic reconstruction in Event Intelligence, Discovery Entry, Event
  Discovery translation, Option-Chain Discovery, and Futu request validation
  migrates to the exact new nested shape together; and
- tests must fail any mixed v0.1/v0.2 result, handoff, or constructor-bypassed
  object before downstream work.

Existing immutable v0.1 results remain valid historical records but are not
runtime inputs after the cutover. A caller wishing to revisit one must
construct and assess a fresh v0.2 submission; no v0.1 object is upgraded or
wrapped in place.

Because Option-Chain Discovery gains a new stable failure semantic while
preserving bounded behavior, its implementation contract advances from v0.2
to v0.3. `EventUnderlyingHypothesis` exact fields, intrinsic reconstruction,
public field tests, adapters, and synthetic fixtures must migrate together.
No persistence migration is currently required because the repository has no
durable serialized Event Intelligence store.

## Four-case adversarial matrix

| Case | Historical result | v0.2 temporal evidence | Event Intelligence v0.2 | Option Discovery |
| --- | --- | --- | --- | --- |
| Bounded FOMC-to-SPY | `ACCEPTED`; completed downstream exercise | Existing complete caller-declared MVP-assumption `expected_window`; no reassessment required | Must remain `ACCEPTED` with unchanged stale boundary | Ready when current; unchanged maturity anchor and interval |
| NVDA power/credit second-order | `INCOMPLETE / incomplete_expected_window` | No reassessment date is assigned by this contract. A fresh submission may use only an explicit complete reassessment under one allowed basis kind | Remains historically unchanged; fresh v0.2 result is accepted only if all new temporal rules are satisfied | If currently applicable, structural-only acceptance is not ready: `missing_authoritative_maturity_anchor`; if stale, stale failure wins |
| NVDA compute-financing narrative | `INCOMPLETE / incomplete_expected_window` | "Over time" and capital-mobilization aims supply neither impact end nor reassessment deadline | Same rule; no retroactive promotion | Same currently-applicable/stale precedence |
| IONQ/SkyWater vertical integration | `INCOMPLETE / incomplete_expected_window` | Acquisition completion is an event date, not an integration-impact end or automatic reassessment deadline | Same rule; no retroactive promotion | Same currently-applicable/stale precedence |

The three historical results and their original payload semantics remain
unchanged. This contract records no reassessment date for them and does not
claim they are now accepted.

The later focused suite must encode these rows as executable assertions rather
than prose-only examples. It must prove: the FOMC fixture remains accepted and
derives byte-for-byte-equivalent request boundaries; each historical fixture
retains its original v0.1 status in the historical record; no fresh v0.2 fixture
is accepted without an explicitly supplied valid reassessment or complete
impact window; a current structural-only fixture fails request construction
with exactly `missing_authoritative_maturity_anchor`; and an otherwise equal
stale structural fixture fails stale before the missing-anchor check.

## Hidden-prediction failure modes

The BUILD and independent review must reject:

- relabeling `reassessment_by` as an expected impact end;
- rendering it as an event date, holding period, expiration preference, or
  recommendation;
- automatic calendar offsets, including generic 30/60/90-day defaults;
- LLM-estimated narrative duration or inferred roll-forward;
- using lease length, deployment year, acquisition completion, publication
  time, or observation time as an unstated substitute;
- a caller-policy assumption represented as a source fact;
- source-backed basis without a source-stated exact milestone date;
- a later reassessment date extending a bounded expected window;
- automatic mutation or renewal after expiry;
- treating Event Intelligence `ACCEPTED` as Option Discovery `READY`; and
- using `reassessment_by` as a maturity anchor.

## BUILD boundary

The later v0.2 BUILD is limited to the exact records, acceptance semantics,
chronology, applicability gate, stable missing-anchor failure, migrations, and
tests frozen here. It must not add monitoring, scheduling, alerts, persistence,
UI, generic workflow state, option generation, ranking, recommendation,
market-data feedback, or Engine evidence work.
