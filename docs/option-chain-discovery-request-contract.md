# Option-Chain Discovery Request Contract v0.4

> Implementation status: implemented. The v0.4 atomic migration is governed by
> [Structural Narrative Option Research Activation Contract v0.1](structural-narrative-option-research-activation-contract.md).
> It preserves the v0.3 bounded-event path while adding explicit neutral
> structural research with `NOT_ESTABLISHED` maturity alignment. The historical
> v0.3 migration from v0.2 was required by the
> [Event Intelligence Temporal Semantics Contract v0.2](event-intelligence-temporal-semantics-v0.2-contract.md)
> for structural-only hypotheses and the stable
> `missing_authoritative_maturity_anchor` failure. Bounded-event behavior is
> unchanged under the compatibility default.

## Purpose

This Tier-A contract defines a provider-neutral request for later option-chain
discovery. It consumes one validated `DiscoveryEntryHandoff` and one explicit
caller evaluation date. It does not call a provider or claim that any listed
expiration or contract is eligible.

The direct module `convexity_hunter.option_chain_discovery` exports exactly:

```python
OptionMaturityAuthority
HypothesisMaturityAlignment
OptionChainDiscoveryRequest
OptionResearchMaturityContext
create_option_chain_discovery_request
```

None of these names is exported from the package root.

## Exact record and function

```python
@dataclass(frozen=True)
class OptionChainDiscoveryRequest:
    discovery_entry_handoff: DiscoveryEntryHandoff
    evaluation_date: datetime.date
    maturity_authority: OptionMaturityAuthority = OptionMaturityAuthority.HYPOTHESIS_ALIGNED


def create_option_chain_discovery_request(
    discovery_entry_handoff: DiscoveryEntryHandoff,
    *,
    evaluation_date: datetime.date,
    maturity_authority: OptionMaturityAuthority = OptionMaturityAuthority.HYPOTHESIS_ALIGNED,
) -> OptionChainDiscoveryRequest:
    ...
```

The record stores exactly those three fields and retains the exact handoff by
identity. The caller supplies a date-only evaluation date; the implementation
reads no clock. The exact enums, context record, authority-specific formulas,
failure precedence, and propagation semantics are frozen in the activation
contract.

## Temporal applicability gate

Before request construction and before expiration-boundary arithmetic, the
selected accepted hypothesis must still be applicable for current discovery.
The inclusive applicability boundary is derived from complete temporal
records:

```text
complete expected_window only -> expected_window.end_date
complete reassessment only -> reassessment.reassessment_by
both complete -> min(expected_window.end_date, reassessment.reassessment_by)
```

The boundary day is valid. For otherwise valid inputs,
`evaluation_date` later than the derived boundary fails closed with
`ValueError` because the selected hypothesis is expired for that evaluation
date. A currently applicable structural-only hypothesis using the compatibility
default or explicit `HYPOTHESIS_ALIGNED` authority then fails with exactly
`missing_authoritative_maturity_anchor`. An explicitly requested
`NEUTRAL_STRUCTURAL_RESEARCH` request instead requires an absent impact window
and complete reassessment and proceeds with `NOT_ESTABLISHED` alignment.

The request never extends, rolls, or substitutes the accepted event window. A
reassessment date never supplies the maturity anchor or extends a bounded
impact window. If an event is expected to have longer-lived effects, Event
Intelligence must express that upstream through a longer explicit,
source-auditable `expected_window` before a new accepted handoff is created.

## Derived request boundaries

Read-only properties expose only values already retained by the handoff or
deterministically derived from the locked MVP maturity policy:

```text
underlying_key = selected hypothesis underlying_key
distribution_mode = selected hypothesis distribution_mode
event_window_end_date = selected hypothesis expected_window.end_date
    for HYPOTHESIS_ALIGNED; otherwise None

HYPOTHESIS_ALIGNED minimum_expiration_date = max(
    evaluation_date + 30 calendar days,
    event_window_end_date + 30 calendar days,
)

NEUTRAL_STRUCTURAL_RESEARCH minimum_expiration_date =
    evaluation_date + 30 calendar days

maximum_expiration_date = evaluation_date + 150 calendar days
```

Both expiration boundaries are inclusive. A later expiration `E` satisfies
this request exactly when `minimum_expiration_date <= E <=
maximum_expiration_date`. The event-buffer rule applies only to
`HYPOTHESIS_ALIGNED`; neutral structural research claims only the 30–150
calendar DTE interval. An empty interval fails request construction.

The request does not encode short/core/long presentation bands because those
bands do not change the hard eligibility interval and are not rankings.

## Standard-monthly evidence boundary

Complete exact-deliverable proof is not required for this request to exist. A
later provider gate may treat exact authoritative `MONTH` expiration evidence
plus exact provider `STANDARD` series classification as a provider-classified
series eligibility claim. That claim remains distinct from proof of an exact
standard or unadjusted deliverable.

Futu `STANDARD`, multiplier, and exercise type do not complete
`OptionContractReference`, `deliverable_id`, settlement, `StructureCosts`, or
research readiness. Those fields remain fail-closed exactly as before. The
provider-neutral standard-monthly definition, Tiger-equivalence rules, and
provider response taxonomy belong to a later chain-evidence contract, not this
request-only unit.

## Validation and failure boundary

The handoff and evaluation date require exact types. The handoff is
intrinsically reconstructed through its existing constructor without replaying
Event Intelligence acceptance. The accepted hypothesis must retain exact
`UnderlyingKey` and `DistributionChangeMode`, and any reassessment must be
complete. After those intrinsic semantics are validated, temporal applicability
is checked before authority admissibility and date arithmetic. Missing
semantics, malformed or constructor-bypassed records, an expired hypothesis,
the missing aligned anchor, a neutral request with a complete impact window,
date overflow, and an empty interval fail with controlled `TypeError` or
`ValueError`.

## Non-goals

This work adds no provider call, chain response, eligibility result, clock,
event adapter, automatic selection, ranking, expiration selection,
Strike/Delta/ATM policy, contract generation, quote, reference completion,
market data, pricing, costs, liquidity, Greeks, candidate assembly, screening,
reporting, recommendation, persistence, monitoring, or execution.
