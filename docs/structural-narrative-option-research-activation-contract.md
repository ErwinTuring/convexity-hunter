# Structural Narrative Option Research Activation Contract v0.1

## Status

This Tier-A contract is frozen and implemented as one atomic runtime migration.
Option-Chain Discovery Request v0.4 now supports the two exact authorities
defined below. The historical v0.3 behavior remains available through the
compatibility-default `HYPOTHESIS_ALIGNED` path.

Independent contract review passed after closing exact API, context-binding,
current-versus-successor wording, compound-failure precedence, and enum-
rendering ambiguities. Independent BUILD review initially found one stale
renderer-signature assertion and missing intrinsic revalidation for
constructor-bypassed maturity contexts. Both were corrected; targeted
re-review passed, as did 91 focused tests, the 1,348-test full suite,
compileall, and `git diff --check`.

The contract permits an accepted, current structural hypothesis to open a
neutral exact-contract Browser without inventing an expected impact end. It
does not authorize automatic structure generation or claim that a selected
expiration matches the narrative's duration.

## Decision: one request with a closed authority enum

The BUILD must use option B: one `OptionChainDiscoveryRequest` with an exact
closed maturity-authority enum. Two request types would duplicate the same
handoff, applicability, provider-retrieval, chain-evidence, Browser, and
selection boundaries and create avoidable drift between them. A mandatory
closed value makes the semantic branch explicit while preserving one request
identity through the existing evidence path.

The target module is exactly `convexity_hunter.option_chain_discovery`. Its
direct-module `__all__` becomes exactly, in order:

```python
__all__ = (
    "OptionMaturityAuthority",
    "HypothesisMaturityAlignment",
    "OptionChainDiscoveryRequest",
    "OptionResearchMaturityContext",
    "create_option_chain_discovery_request",
)
```

None of these names is re-exported from the package root. The target records
and enums are:

```python
class OptionMaturityAuthority(str, Enum):
    HYPOTHESIS_ALIGNED = "hypothesis_aligned"
    NEUTRAL_STRUCTURAL_RESEARCH = "neutral_structural_research"


class HypothesisMaturityAlignment(str, Enum):
    ESTABLISHED = "established"
    NOT_ESTABLISHED = "not_established"


@dataclass(frozen=True)
class OptionChainDiscoveryRequest:
    discovery_entry_handoff: DiscoveryEntryHandoff
    evaluation_date: datetime.date
    maturity_authority: OptionMaturityAuthority = (
        OptionMaturityAuthority.HYPOTHESIS_ALIGNED
    )

    @property
    def hypothesis_maturity_alignment(self) -> HypothesisMaturityAlignment: ...

    @property
    def event_window_end_date(self) -> Optional[datetime.date]: ...
```

`event_window_end_date` returns the exact accepted end date for
`HYPOTHESIS_ALIGNED` and `None` for `NEUTRAL_STRUCTURAL_RESEARCH`. It is never
filled from reassessment, a provider expiration, or a selected contract.

The factory signature becomes exactly:

```python
def create_option_chain_discovery_request(
    discovery_entry_handoff: DiscoveryEntryHandoff,
    *,
    evaluation_date: datetime.date,
    maturity_authority: OptionMaturityAuthority = (
        OptionMaturityAuthority.HYPOTHESIS_ALIGNED
    ),
) -> OptionChainDiscoveryRequest: ...
```

Existing bounded-event callers therefore retain their current source behavior.
A structural-only caller must explicitly request
`NEUTRAL_STRUCTURAL_RESEARCH`; absence of an authority value never silently
selects that path. Exact field, enum, and direct-construction validation remain
mandatory.

`hypothesis_maturity_alignment` is derived, not independently stored:

```text
HYPOTHESIS_ALIGNED           -> ESTABLISHED
NEUTRAL_STRUCTURAL_RESEARCH -> NOT_ESTABLISHED
```

This prevents contradictory authority/alignment combinations.

## Shared acceptance and applicability gate

Both authorities require the exact existing accepted Discovery Entry handoff,
one exact caller `evaluation_date`, a resolved underlying, and a supported
distribution mode. Request construction reads no clock and performs no
provider call.

The existing inclusive stale-hypothesis gate remains authoritative:

```text
complete expected_window only -> expected_window.end_date
complete reassessment only    -> reassessment.reassessment_by
both complete                 -> min(the two dates)
```

The boundary day remains current. A later evaluation date fails before
maturity arithmetic. Reassessment expiry always requires a fresh submission,
assessment, and handoff; no request extends or rolls any temporal record.

## Authority 1: HYPOTHESIS_ALIGNED

`HYPOTHESIS_ALIGNED` requires a complete accepted expected impact window. Its
inclusive interval remains exactly:

```text
minimum_expiration_date = max(
    evaluation_date + 30 calendar days,
    expected_window.end_date + 30 calendar days,
)

maximum_expiration_date = evaluation_date + 150 calendar days
```

The existing bounded-event behavior, event buffer, empty-interval failure,
provider retrieval, Browser filtering, and human selection remain unchanged.
`ESTABLISHED` means only that the selected expiration satisfies this declared
policy relative to the accepted expected impact window. It does not mean
optimal, preferred, recommended, correctly priced, or guaranteed to capture
the impact.

If this authority is requested without a complete expected impact window,
construction fails with the existing exact reason:

```text
missing_authoritative_maturity_anchor
```

## Authority 2: NEUTRAL_STRUCTURAL_RESEARCH

`NEUTRAL_STRUCTURAL_RESEARCH` is valid only when all four conditions hold:

1. Event Intelligence is `ACCEPTED` through the exact retained handoff;
2. `expected_window` is absent, not partial or complete;
3. one complete atomic `HypothesisReassessment` is present; and
4. `evaluation_date <= reassessment.reassessment_by`.

Its inclusive Browser interval is only the existing neutral research policy:

```text
minimum_expiration_date = evaluation_date + 30 calendar days
maximum_expiration_date = evaluation_date + 150 calendar days
```

There is no event-buffer calculation because there is no authoritative impact
end. The machine-readable state is exactly:

```text
hypothesis_maturity_alignment = NOT_ESTABLISHED
```

The interval claims only that an expiration lies inside the product's neutral
30--150 DTE research range. It makes no claim about narrative duration,
expected impact, contract attractiveness, preferred maturity, or holding
period. No expiration is selected by default.

A complete `expected_window` makes this path invalid. The caller must use
`HYPOTHESIS_ALIGNED`; it may not discard the stronger bounded-event authority
to obtain a wider lower boundary. The stable failure is:

```text
neutral_structural_research_requires_absent_expected_window
```

The existing `missing_authoritative_maturity_anchor` reason is not emitted for
an explicitly requested, otherwise valid neutral structural Browser path.

## Validation order

The BUILD freezes this order:

1. exact request, enum, handoff, accepted-result, selected-hypothesis, resolved-
   underlying, and distribution-mode validation, including exact intrinsic
   reconstruction of the accepted v0.2 handoff;
2. complete/absent temporal-record classification;
3. the shared inclusive stale-hypothesis gate;
4. authority-specific admissibility checks above;
5. authority-specific date arithmetic and empty-interval validation; and
6. construction of one immutable request.

This order preserves stale-before-maturity behavior. Constructor-bypassed or
partially populated temporal records fail during exact handoff reconstruction
rather than being treated as absent.

Compound cases are closed as follows:

- a partial `expected_window` can produce only an `INCOMPLETE` Event
  Intelligence result, so it cannot inhabit an exact accepted handoff; request
  construction fails intrinsic handoff validation before any authority reason;
- neutral plus a complete expected window checks stale applicability first,
  then always fails
  `neutral_structural_research_requires_absent_expected_window`, regardless of
  whether reassessment is present;
- expected window absent plus reassessment absent cannot inhabit an accepted
  v0.2 handoff and therefore fails intrinsic handoff validation; no second
  stable maturity reason is introduced for that unreachable state; and
- hypothesis-aligned plus an absent impact window and complete reassessment
  checks stale applicability first, then fails exactly
  `missing_authoritative_maturity_anchor`.

## Authorities that never establish maturity

None of the following may create, substitute for, or upgrade maturity
authority:

- `reassessment_by`, which remains applicability and research-governance
  authority only;
- `expected_holding_days`, which remains downstream holding design only;
- provider-listed expirations or provider expiration-cycle classifications;
- Browser ordering or visibility;
- a human-selected expiration; or
- a later successful exact-contract verification.

In particular, human selection inside a neutral Browser retains
`NOT_ESTABLISHED`; it never retroactively creates an expected impact window or
hypothesis-aligned maturity.

## Lossless downstream propagation

The alignment state must not enter `CandidateResearchRecord`, pricing inputs,
Engine evidence, costs, liquidity, or calculation lineage. It is a separate
research-context disclosure.

The existing Futu chain evidence already retains the exact discovery request;
the Browser retains that evidence; and the selection retains the Browser and
the exact selected structure. These layers continue retaining those objects by
identity. Their future contract wording must make request bounds authority-
specific rather than unconditionally requiring an event-window buffer. They
do not add copied enum fields; authority and alignment remain reachable from
the one retained request.

At the selection-to-Direct-Entry bridge, the BUILD adds one provider-neutral
atomic binding:

```python
@dataclass(frozen=True)
class OptionResearchMaturityContext:
    discovery_request: OptionChainDiscoveryRequest
    structure: OptionStructure

    @property
    def maturity_authority(self) -> OptionMaturityAuthority: ...

    @property
    def hypothesis_maturity_alignment(
        self,
    ) -> HypothesisMaturityAlignment: ...
```

The context retains the exact request and exact selected structure by identity
and validates that every leg has the request underlying and an expiration
inside its inclusive bounds. It derives both enum values from the request and
cannot accept caller-supplied alignment text.

The Futu bridge contract advances to v0.2. Its result appends exactly one field:

```python
@dataclass(frozen=True)
class FutuExactContractSelectionVerification:
    selection: FutuExactContractSelection
    contract_verifications: tuple[FutuExactOptionContractVerification, ...]
    direct_entry_exact_contract_verification: DirectEntryExactContractVerification
    maturity_context: OptionResearchMaturityContext
```

After revalidating the exact selection and before any provider call, the bridge
constructs the context with exactly:

```python
OptionResearchMaturityContext(
    selection.browser.discovery_evidence.discovery_request,
    selection.structure,
)
```

Direct construction of the bridge result must require
`maturity_context.discovery_request is
selection.browser.discovery_evidence.discovery_request` and
`maturity_context.structure is selection.structure`. The existing ordered
provider verification and provider-neutral exact-contract checks then run
unchanged. The returned result retains that same context object by identity.
This migration adds or reorders no Futu direct-module name. At this migration
checkpoint, `__all__` contained the existing exact 22 names; later additive
provider evidence APIs do not change this migration contract.

The Direct Entry service contract advances to v0.3. Its result appends exactly:

```python
maturity_context: Optional[OptionResearchMaturityContext]
```

It follows the existing `offline_service_result` field, so the target exact
four-field order is exact-contract verification, research-readiness
verification, offline-service result, then maturity context. The direct-module
`__all__` remains its existing exact two names.

Its existing function signature appends this required keyword-only argument
after `position_management_plan_request`:

```python
*,
maturity_context: Optional[OptionResearchMaturityContext]
```

Every caller must therefore consciously pass an exact context or explicit
`None`. Before exact-contract verification, a present context requires exact
type and `maturity_context.structure is structure`. A Discovery Entry caller
must pass the exact `maturity_context` retained by its selection-verification
result; replacing it or passing `None` violates this contract. Generic Direct
Entry passes `None` because it has no Event Intelligence maturity claim.

The offline single-structure service contract advances to v0.2. Its result
appends the exact field:

```python
maturity_context: Optional[OptionResearchMaturityContext]
```

It follows the existing `report_markdown` field, so the target exact
five-field order preserves all four current fields first. The direct-module
`__all__` remains its existing exact three names.

Its service signature likewise appends one required keyword-only
`maturity_context` argument. Before screening, a present context requires exact
type and `maturity_context.structure is assembly_result.record.structure`.
The service retains the same object by identity and passes it unchanged to the
renderer. The Direct Entry service must pass its exact input context into this
call and retain the exact offline result context.

The report renderer signature becomes exactly:

```python
def render_candidate_markdown(
    candidate: CandidateResearchRecord,
    locale: str = "en",
    screening_decision: Optional[ScreeningDecision] = None,
    position_management_plan_result: Optional[
        PositionManagementPlanResult
    ] = None,
    maturity_context: Optional[OptionResearchMaturityContext] = None,
) -> str: ...
```

It validates a present exact context and requires
`maturity_context.structure is candidate.structure` before rendering. The
default preserves direct generic renderer calls; the offline service always
passes its context explicitly. No layer may convert `NOT_ESTABLISHED` to
`ESTABLISHED`, reconstruct an equal replacement, or infer alignment from the
selected expiration.

The generic service cannot infer whether a caller intentionally stripped its
Discovery provenance without adding a new orchestration identity. This freeze
does not add such a framework. Instead, the Futu bridge makes context
non-optional, both service boundaries make the caller's choice explicit, and
end-to-end Discovery tests require exact object identity at every retained
boundary.

Context type failures use controlled `TypeError`. Identity or economic-binding
failures use `ValueError`: the bridge uses exact
`maturity_context_request_mismatch` or `maturity_context_structure_mismatch`;
the Direct Entry service, offline service, and renderer use exact
`maturity_context_structure_mismatch`. Context checks occur before provider
calls at the bridge, before exact-contract verification at Direct Entry,
before screening in the offline service, and before any report line is
rendered.

This sidecar is the smallest propagation change: it avoids adding Event
Intelligence semantics to the provider-neutral candidate or Engine records and
does not create a new orchestration framework.

## Chinese report disclosure

When the context is present, the Chinese report includes a dedicated
"假设与到期日的时间匹配" disclosure. The semantic content is frozen:

- `ESTABLISHED`: the expiration satisfies the declared bounded-event maturity
  policy relative to the accepted expected impact window; this is not an
  optimality, pricing, preference, or recommendation claim.
- `NOT_ESTABLISHED`: the expiration entered research only through the neutral
  30--150 DTE policy and explicit human selection; no match to narrative
  duration or expected impact has been established, and no preferred or
  recommended expiry is implied.

The report renders enum member names with `.name`, exactly `ESTABLISHED` or
`NOT_ESTABLISHED`, alongside the Chinese explanation. Serialized enum `.value`
strings remain lowercase and are not labeled as the displayed machine state.
The report also renders the authority through its exact enum `.name`. The
exact Chinese lines are:

```text
### 假设与到期日的时间匹配

HYPOTHESIS_ALIGNED:
- 假设到期日匹配状态：已建立（ESTABLISHED）
- 期限依据：预期影响窗口（HYPOTHESIS_ALIGNED）
- 说明：该到期日仅满足相对于已接受预期影响窗口的既定期限政策；不表示最优、偏好、定价合理或投资建议。

NEUTRAL_STRUCTURAL_RESEARCH:
- 假设到期日匹配状态：未建立（NOT_ESTABLISHED）
- 期限依据：中性结构性研究（NEUTRAL_STRUCTURAL_RESEARCH）
- 说明：该到期日仅因处于既定 30–150 DTE 中性研究范围并经用户明确选择而进入研究；不表示其匹配叙事持续时间或预期影响，也不表示优选或建议到期日。
```

Only the matching three bullets are rendered. The labels
`HYPOTHESIS_ALIGNED:` and `NEUTRAL_STRUCTURAL_RESEARCH:` above identify the
contract branches and are not report lines. The report must not render
`reassessment_by` as an impact end or maturity anchor. When the context is
`None`, the section is omitted; generic Direct Entry must not manufacture an
Event Intelligence alignment statement.

## Compatibility and migration

This is one atomic contract migration:

- Option-Chain Discovery Request advances from v0.3 to v0.4;
- existing bounded requests default to `HYPOTHESIS_ALIGNED` and retain
  byte-for-byte-equivalent date boundaries;
- Futu chain evidence, Browser, and bridge fixtures migrate to the three-field
  request while retaining their existing economic and provider semantics;
- the Futu bridge advances to v0.2, Direct Entry service to v0.3, and offline
  service to v0.2 with the exact fields/signatures above; the renderer adds the
  exact fifth parameter above;
- no historical acceptance result, discovery exercise, or report is rewritten.

No persistence migration is required because the repository has no durable
serialized request store. Public API ordering, exact field order, function
signatures, and contract version increments must be frozen in the BUILD diff
and tested before release.

## Adversarial matrix

| Case | Requested authority | Result |
| --- | --- | --- |
| Current bounded FOMC hypothesis | `HYPOTHESIS_ALIGNED` or compatibility default | Existing interval; `ESTABLISHED` |
| Current bounded FOMC hypothesis | `NEUTRAL_STRUCTURAL_RESEARCH` | Fail: `neutral_structural_research_requires_absent_expected_window` |
| Current structural-only hypothesis with complete reassessment | `HYPOTHESIS_ALIGNED` | Fail: `missing_authoritative_maturity_anchor` |
| Current structural-only hypothesis with complete reassessment | `NEUTRAL_STRUCTURAL_RESEARCH` | Neutral 30--150 DTE interval; `NOT_ESTABLISHED` |
| Structural-only hypothesis after reassessment date | either authority | Fail stale before authority arithmetic |
| Structural-only hypothesis without complete reassessment | neutral | Fail intrinsic accepted-handoff validation; no request |
| Human selects a listed neutral-path expiry | neutral | Alignment remains `NOT_ESTABLISHED` through report |
| Generic Direct Entry with no discovery context | none | Existing behavior; no alignment section |

Focused BUILD tests must prove exact enum closure, compatibility defaults,
direct-construction invariants, both formulas and inclusive boundaries, stale
precedence, non-bypass behavior, stable failures, context identity and
structure binding, end-to-end non-upgrade, exact Chinese disclosure, and
unchanged generic Direct Entry output.

## Non-goals and implementation boundary

The implementation is limited to the closed enum branch, deterministic
interval arithmetic, atomic context propagation, report disclosure,
migrations, and tests described here.

It must not add ranking, scoring, a default expiration, ATM or Delta selection,
recommendation, automatic Candidate Generation, provider routing, market-data
feedback, new costs/liquidity/Greeks evidence, monitoring, persistence,
scheduling, or execution.
