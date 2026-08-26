# Discovery Entry Handoff Contract v0.1

> Historical v0.1 record shape. The implemented handoff consumes the v0.2
> acceptance result from the frozen
> [Event Intelligence Temporal Semantics Contract v0.2](event-intelligence-temporal-semantics-v0.2-contract.md)
> and requires `event-intelligence-acceptance-v0.2`; there is no dual-version
> handoff or implicit upgrade of historical v0.1 results.

## Purpose

This Tier-A contract defines the smallest deterministic handoff from one
already accepted Event Intelligence result to later discovery work. It proves
only that the caller explicitly selected one hypothesis retained by that
accepted result. It does not discover, rank, map, retrieve, price, or generate
anything.

The direct module `convexity_hunter.discovery_entry` exports exactly:

```python
DiscoveryEntryHandoff
create_discovery_entry_handoff
```

Neither name is exported from the package root.

## Exact record and function

```python
@dataclass(frozen=True)
class DiscoveryEntryHandoff:
    acceptance_result: EventIntelligenceAcceptanceResult
    selected_hypothesis: EventUnderlyingHypothesis


def create_discovery_entry_handoff(
    acceptance_result: EventIntelligenceAcceptanceResult,
    selected_hypothesis: EventUnderlyingHypothesis,
) -> DiscoveryEntryHandoff:
    ...
```

The result retains both exact caller objects by identity. It duplicates no
event ID, hypothesis ID, underlying identity, impact path, distribution mode,
window, or issue state. The caller selects an exact hypothesis object; the
handoff never chooses one by order, ID, score, or model judgment.

## Preconditions

Both arguments require exact types. The acceptance result must retain exact
status `ACCEPTED`, an exact empty issue tuple, assessment version
`event-intelligence-acceptance-v0.2`, and an intrinsically valid exact
`EventIntelligenceSubmission`. The selected hypothesis must be an identity
member of that submission's retained hypothesis tuple. Equality, a matching
ID, or an equal copy from another result is insufficient.

The handoff reconstructs only the submission's intrinsic record graph through
the existing `EventIntelligenceSubmission` constructor. This verifies exact
nested types, canonical structure, identities, references, chronology, and an
acyclic dependency graph. Constructor bypasses and missing fields fail with a
controlled `TypeError` or `ValueError`; `AttributeError` does not escape.

Incomplete acceptance, nonempty issues, the wrong version, malformed retained
structure, or a hypothesis not retained by identity raises `ValueError`.
Wrong exact types and subclasses raise `TypeError`. There is no fallback,
optional handoff, new status, or custom exception.

## No semantic replay

The handoff must not call `assess_event_intelligence_submission`, private issue
derivation, or the `EventIntelligenceAcceptanceResult` constructor. It trusts
the already-issued terminal proof fields after intrinsic submission validation
and does not re-author source closure, impact, distribution, contradiction,
uncertainty, or falsification semantics.

Python permits `object.__new__` to forge a structurally valid object with
arbitrary terminal fields. Distinguishing that case without semantic replay
would require a signature, capability token, or a changed acceptance-result
contract. That stronger anti-forgery guarantee is explicitly outside this
handoff rather than silently introducing a second acceptance algorithm.

## Non-goals

This work adds no event source or adapter, Skill, LLM, prompt, mapping,
automatic selection, ranking, option-chain retrieval, contract verification,
expiration/Strike/Delta policy, structure generation, market data, candidate
assembly, screening, report, persistence, UI, monitoring, recommendation, or
execution behavior.
