# Futu Exact Contract Browser Contract v0.1

> Implementation status: implemented. The separately frozen
> [Structural Narrative Option Research Activation Contract v0.1](structural-narrative-option-research-activation-contract.md)
> defines a future neutral structural request and lossless maturity-alignment
> propagation. It is not yet runtime behavior.

## Purpose

This Tier-A contract closes the human-selection gap between one accepted
source-backed underlying and the existing Direct Entry path. It exposes a
neutral browser over exact listed Futu contracts and records one explicit
human choice as unverified research intent.

It is not Candidate Generation. Browser visibility does not mean that a
contract is attractive, cheap, liquid, compatible with a distribution mode,
or qualified for research.

The direct module `convexity_hunter.providers.futu` adds exactly, in order:

```text
FutuExactContractBrowser
FutuExactContractSelection
create_futu_exact_contract_browser
select_futu_exact_contracts
```

Nothing is re-exported from a package module.

## Exact records and functions

```python
@dataclass(frozen=True)
class FutuExactContractBrowser:
    discovery_evidence: FutuOptionChainDiscoveryEvidence

    @property
    def rows(self) -> tuple[FutuOptionChainContractEvidence, ...]: ...


@dataclass(frozen=True)
class FutuExactContractSelection:
    browser: FutuExactContractBrowser
    selected_contracts: tuple[FutuOptionChainContractEvidence, ...]
    structure: OptionStructure


def create_futu_exact_contract_browser(
    discovery_evidence: FutuOptionChainDiscoveryEvidence,
) -> FutuExactContractBrowser: ...


def select_futu_exact_contracts(
    browser: FutuExactContractBrowser,
    *,
    provider_identifiers: tuple[str, ...],
    assumed_portfolio_value: float,
    expected_holding_days: int,
    quantity: int = 1,
) -> FutuExactContractSelection: ...
```

The Browser retains the exact discovery evidence by identity. The Selection
retains the exact Browser and exact selected evidence rows by identity.

## Browser visibility

`rows` contains all and only discovery-evidence contracts satisfying every
condition below:

```text
provider_expiration_cycle == MONTH
provider_standard_type == STANDARD
suspension == False
statuses == (ELIGIBLE,)
option_type is Call or Put
```

The currently implemented v0.3 `OptionChainDiscoveryRequest` enforces both
inclusive maturity rules:

```text
30 <= DTE <= 150
expiration >= event_window_end + 30 calendar days
```

Browser construction revalidates the complete discovery evidence rather than
weakening or recomputing those request boundaries.

When the frozen Structural Narrative Option Research Activation BUILD lands,
this contract advances to v0.2 and Browser construction continues to consume
the exact request bounds without recomputation. A `HYPOTHESIS_ALIGNED` request
retains both rules above. An explicit `NEUTRAL_STRUCTURAL_RESEARCH` request has
no event-window end and therefore enforces only its inclusive neutral 30--150
DTE bounds. Every neutral row retains
`hypothesis_maturity_alignment = NOT_ESTABLISHED`; visibility or human
selection cannot upgrade it.

Rows preserve the evidence order: expiration, strike, Call before Put, then
provider identifier. This is neutral navigation only. No row is selected by
default, hidden, scored, or ranked.

Futu `STANDARD` remains a provider classification. Browser visibility does
not establish exact OCC deliverables, settlement, completed reference terms,
quote freshness, liquidity, research readiness, or recommendation semantics.

## Explicit human selection

The caller must provide one or two unique identifiers visible in the exact
Browser. Unknown, hidden, duplicate, copied, or cross-Browser rows fail closed.
The Selection canonicalizes retained rows to neutral Browser order while
preserving each exact evidence object.

One selected row creates one unverified Long Call or Long Put research-intent
structure. Two rows are accepted only when the user explicitly selected one
Call and one Put with the same provider underlying, expiration, strike, and
lot size. That pair creates one unverified Long Straddle research-intent
structure. No Straddle is inferred or preselected by the Browser.

The provider lot size becomes the `OptionLeg.contract_multiplier`. The caller
supplies quantity, assumed portfolio value, and expected holding days. A
provider Decimal strike must round-trip exactly through the existing
float-based `OptionLeg`; otherwise selection fails rather than changing the
economic identity.

The produced `OptionStructure` means only:

> The user explicitly requests research on this exact listed structure.

It is not source-backed exact verification. Later Futu exact verification must
produce matching `OptionContractReference` evidence, and existing Direct Entry
must call `verify_direct_entry_exact_contracts` before Candidate Assembly.

## Non-goals

This unit adds no provider call, snapshot, BBO, quote, freshness, ATM, Delta,
Greeks, IV, activity, liquidity, cheapness, attractiveness, recommendation,
default contract, automatic selection, Candidate Generation, reference
completion, Direct Entry invocation, Candidate Assembly, screening, report,
persistence, monitoring, trading, provider routing, or Tiger change.
