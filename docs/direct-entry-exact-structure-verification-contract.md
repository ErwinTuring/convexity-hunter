# Deterministic Direct-Entry Exact-Structure Verification Contract

## 1. Status and authority

This document is the canonical documentation-only freeze for Deterministic
Direct-Entry Exact-Structure Verification at contract base
`584e99908c4b9b8e330ce3bbe00d5ef9ab578924`. It does not itself authorize
implementation, source changes, test changes, staging, commits, pushes, or
network access.

The capability verifies that one complete caller-supplied `OptionStructure`
corresponds to authentic reviewed cost and liquidity evidence. It is a narrow
verification boundary, not a direct-entry eligibility engine and not an
incomplete-description resolution path. The implementation and focused tests
must support Python 3.9.

## 2. Public API and export boundary

The authoritative direct module is:

```text
convexity_hunter.direct_entry_verification
```

Its public names are exactly these two names, in this order:

1. `DirectEntryExactStructureVerification`
2. `verify_direct_entry_exact_structure`

The module's `__all__` must contain exactly those two names in that order. It
has no other public class, function, result, policy, enum, constant, alias,
or convenience wrapper. The package root exports zero names from this
capability; neither name may be added to `convexity_hunter.__init__`.

The dependency types remain the existing types from the existing modules:
`OptionStructure`, `StructureCostsTransformationResult`, and
`StructureLiquidityTransformationResult`. This freeze adds no replacement
type and changes no existing type or producer contract.

## 3. Frozen result and function signature

`DirectEntryExactStructureVerification` is a frozen dataclass with exactly
these fields, in this order, and no additional fields:

```python
@dataclass(frozen=True)
class DirectEntryExactStructureVerification:
    structure: OptionStructure
    costs_result: StructureCostsTransformationResult
    liquidity_result: StructureLiquidityTransformationResult
```

The only function is exactly:

```python
def verify_direct_entry_exact_structure(
    structure: OptionStructure,
    costs_result: StructureCostsTransformationResult,
    liquidity_result: StructureLiquidityTransformationResult,
) -> DirectEntryExactStructureVerification:
```

The result contains no record, lineage, calculation ID, calculation time,
generated data, status, eligibility decision, or derived sidecar.

## 4. Exact top-level boundary

Both public construction paths—the direct
`DirectEntryExactStructureVerification(...)` constructor and
`verify_direct_entry_exact_structure(...)`—apply the same exact top-level
boundary and are not alternate trust paths. In the signature order, before
reading any nested attribute, they require:

```text
type(structure) is OptionStructure
type(costs_result) is StructureCostsTransformationResult
type(liquidity_result) is StructureLiquidityTransformationResult
```

`isinstance` is not sufficient. Every subclass and every other object is
rejected. No `.record`, `.lineage`, `.structure`, `.as_of_date`, or other
nested property may be read before all three top-level checks succeed. A
failure returns no result and does not call any downstream transformation,
proof, selection, or retrieval function.

The result constructor must enforce the complete result invariants below; it
is not an unchecked container that can bypass the public function's contract.

## 5. Intrinsic wrapper verification

After the top-level boundary, verify the supplied wrappers in this order:

1. Reconstruct the exact existing
   `StructureCostsTransformationResult` from the supplied
   `costs_result.record` and `costs_result.lineage`.
2. Reconstruct the exact existing
   `StructureLiquidityTransformationResult` from the supplied
   `liquidity_result.record` and `liquidity_result.lineage`.

The reconstruction is equivalent to constructing each existing wrapper from
its original `record` and `lineage`, not to copying, serializing, comparing,
or trusting the wrapper object. The existing wrapper constructors and their
private intrinsic record-to-lineage verifiers remain authoritative for the
complete reviewed schemas, calculation identity, retained evidence,
lineage references, quality flags, and chronology they already own. A
constructor-bypassed or otherwise malformed exact wrapper is rejected when
this reconstruction fails.

The reconstructed wrappers are verification-only and are discarded. The
implementation must not call `transform_structure_costs`,
`transform_structure_liquidity`, or any upstream proof, correction,
freshness, timing, relationship, selection, chain, or retrieval function to
produce or re-prove evidence. Reconstructing the existing wrapper type is the
only permitted intrinsic verification operation; it creates no new lineage
or calculation authority.

## 6. Deterministic validation precedence

Successful and failing calls follow this exact order for both public
construction paths:

1. Exact top-level types in function/field order.
2. Costs-wrapper intrinsic reconstruction and verification.
3. Liquidity-wrapper intrinsic reconstruction and verification.
4. Exact economic structure equality across the three supplied values:
   `structure`, `costs_result.record.structure`, and
   `liquidity_result.record.structure`. Existing `OptionStructure` equality
   is authoritative and covers the complete structure value, including
   ordered legs and all existing structure fields. Equal independently
   constructed structures are accepted; object identity is not required.
5. Shared observation date equality:
   `costs_result.record.as_of_date ==
   liquidity_result.record.as_of_date`.
6. Chronology remains delegated to the two intrinsic wrapper verifiers. It
   may be asserted only as an already-established wrapper invariant and may
   not create a second chronology authority or recompute chronology.

The direct verifier must not catch, reorder, translate, or replace an earlier
failure with a later one. It performs no cross-wrapper comparison of
`calculation_id` or `calculated_at`: cost and liquidity calculation IDs and
calculation timestamps may differ and are not required to match.

## 7. Successful result and non-mutation

On success, return one frozen result retaining the original supplied objects
by identity:

```text
result.structure is structure
result.costs_result is costs_result
result.liquidity_result is liquidity_result
```

The verification-only reconstructed wrappers must never replace the supplied
wrappers in the result. The operation creates no IDs, timestamps, market
data, records, lineage, correction, freshness, timing, relationship,
selection, or transformation output; it obtains no clock; and it does not
mutate any supplied object or nested value.

The proof established by a successful result is only that the complete
caller-supplied exact `OptionStructure` has the same exact economic structure
and shared observation date as two independently authenticated existing
reviewed wrappers. It does not establish full direct-entry eligibility and
does not resolve an incomplete description, infer missing contracts, or
generate a structure.

## 8. Explicit exclusions

This capability contains no:

- provider or network access;
- option-chain retrieval or scanning;
- standard-monthly or DTE policy;
- Delta, ATM, or structure generation;
- pricing;
- Event Intelligence or Skills;
- screening, candidate assembly, report, or service integration;
- UI or CLI;
- persistence;
- monitoring or alerts; or
- execution.

## 9. Later BUILD boundary

This freeze is not a BUILD authorization. If a later BUILD is separately
authorized, its implementation write set is exactly:

```text
src/convexity_hunter/direct_entry_verification.py
tests/test_direct_entry_verification.py
```

No existing source, package-root export, existing test, fixture, or unrelated
documentation may be changed. At BUILD completion only, any edits to
`docs/project-state.md` and `docs/current-checkpoint.md` are status-only;
they may not become new contract or implementation scope.

## 10. Acceptance-test contract

The new focused test file must independently assert all of the following,
using fixed expected values and outcomes rather than treating a second call
or a private implementation helper as the oracle:

- API, exact two-name public API order, exact frozen result field order and
  field types, exact function parameter/return signature, and zero
  package-root exports;
- exact top-level types for both public construction paths, subclass
  rejection, and rejection before any nested property access;
- rejection of constructor-bypassed and malformed costs or liquidity
  wrappers through exact wrapper reconstruction;
- the complete precedence order, including costs intrinsic verification
  before liquidity intrinsic verification and both before structure/date
  correspondence checks;
- acceptance of equal but independently constructed `OptionStructure`
  values, including independently constructed cost/liquidity lineages with
  different valid calculation IDs and timestamps;
- rejection of a structure mismatch and rejection of a shared
  `as_of_date` mismatch;
- identity retention of the caller structure and both original wrappers;
- proof that no upstream transformation, proof, correction, freshness,
  timing, relationship, selection, chain, or retrieval function is called;
- deterministic repeated outcomes, no generated values or clock dependence,
  and no mutation of the supplied objects or their nested values.
