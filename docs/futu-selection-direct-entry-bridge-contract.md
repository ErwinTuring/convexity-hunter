# Futu Selection-to-Direct-Entry Bridge Contract v0.1

## Purpose and boundary

This separate Tier-A contract verifies that one explicit
`FutuExactContractSelection` still resolves to the same real Futu listed
contracts and then applies the existing provider-neutral Direct Entry exact-
contract gate.

It does not change the Exact Contract Browser contract. Browser creation and
selection remain provider-call-free and Direct-Entry-free. Only the explicit
bridge function defined here may perform the later verification step.

The direct module `convexity_hunter.providers.futu` adds exactly, immediately
after the four Browser/selection names:

```text
FutuExactContractSelectionVerification
verify_futu_exact_contract_selection
```

Nothing is re-exported from a package module. The Futu direct-module API then
contains exactly 22 names.

## Exact result and function

```python
@dataclass(frozen=True)
class FutuExactContractSelectionVerification:
    selection: FutuExactContractSelection
    contract_verifications: tuple[FutuExactOptionContractVerification, ...]
    direct_entry_exact_contract_verification: DirectEntryExactContractVerification


def verify_futu_exact_contract_selection(
    quote_context: object,
    selection: FutuExactContractSelection,
) -> FutuExactContractSelectionVerification: ...
```

The result retains the exact selection by identity. Its ordered provider
verifications correspond one-to-one with `selection.selected_contracts` and
retain the exact contract references used by the Direct Entry verification.
The Direct Entry verification retains `selection.structure` by identity.

## Frozen validation and call order

The function performs only these steps:

1. Revalidate the exact `FutuExactContractSelection`, including its retained
   Browser rows and structure binding.
2. For every selected row, in neutral selection order, call the existing
   `verify_futu_monthly_option_contract` exactly once with:
   - the caller's exact `quote_context`;
   - the exact request `UnderlyingKey` retained by the Browser;
   - the row's exact expiration;
   - the row's exact canonical Call/Put value; and
   - the row's exact `Decimal` strike.
3. Fail closed unless every returned `FutuExactOptionContractVerification` is
   intrinsically valid and exactly matches the selected row's provider
   identifier, provider expiration classification, provider standard
   classification, underlying, expiration, option type, strike, and provider
   lot-size/multiplier.
4. Call the existing `verify_direct_entry_exact_contracts` exactly once with
   the exact `selection.structure` and the ordered tuple of exact returned
   `OptionContractReference` objects.
5. Return the frozen three-field sidecar.

The existing Futu verifier remains the sole owner of expiration, chain,
snapshot, exact identity, provider `MONTH`, provider `STANDARD`, suspension,
validity, multiplier, and exercise-type verification. The bridge does not
duplicate or weaken those provider checks.

The existing provider-neutral verifier remains the sole owner of structure-to-
reference economic identity. Incomplete deliverable and settlement semantics
remain incomplete and do not become research readiness.

## Direct-construction invariants

Direct construction of the result revalidates all three values and fails
closed unless:

- the selection has exact type and remains intrinsically valid;
- `contract_verifications` is an exact tuple of the exact provider
  verification type with one item per selected row in the same order;
- every provider verification matches its selected row on every field listed
  above;
- the Direct Entry result has the exact existing result type and is
  intrinsically valid;
- its structure is the exact `selection.structure` object; and
- each retained contract reference is the exact object from the corresponding
  provider verification.

Equal-but-copied selections, rows, provider verifications, structures, or
contract references do not satisfy identity-retention requirements where the
contract requires identity.

## Failure and disclosure behavior

Type and intrinsic-value failures are deterministic `TypeError` or
`ValueError`. Existing provider retrieval and response failures propagate
unchanged and sanitized. The bridge catches no error to substitute a contract,
retry, continue partially, or invoke downstream research.

No credential, account identifier, raw provider payload, or contract catalog
is logged or persisted.

## Non-goals

This unit adds no Browser filtering, default selection, automatic selection,
ATM, Delta, ranking, Candidate Generation, quote, BBO, freshness, activity,
Greeks, IV, liquidity, exact deliverable completion, research-readiness proof,
Candidate Assembly, reviewed-research service invocation, screening, report,
persistence, provider routing, Tiger change, monitoring, recommendation,
trading, or execution.

The sidecar proves only:

> The user's explicit listed-structure selection still resolves exactly and
> passes the existing Direct Entry exact-contract identity gate.
