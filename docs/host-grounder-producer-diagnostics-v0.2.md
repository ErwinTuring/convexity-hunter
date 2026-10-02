# Host Grounder Producer Diagnostics v0.2

Status: **CONTRACT FROZEN — IMPLEMENTED AND INDEPENDENTLY REVIEWED.**
Independent contract and final code reviews passed. No model/source request
or new live attempt is part of this unit.

The one-shot diagnostic stopped at the frozen v0.1 check
`producer_wire_normalization` with `PRODUCER_ENVELOPE_INVALID`. Its exact
parser operation is not established. This proposal adds opt-in local
observability; it does not change acceptance, prompts, budgets, or gates.

## Closed diagnostic contract

On the new v0.3 runtime route only, retain error code
`PRODUCER_ENVELOPE_INVALID` and stage `producer_envelope_normalization`;
allow only these additional, versioned `failure_check` labels:

| `failure_check` | Operation immediately following the check update |
| --- | --- |
| `producer_v0_3_wire_decode` | Bounded wire decode |
| `producer_v0_3_root_shape` | Closed root-shape/version validation |
| `producer_v0_3_catalog_source_validation` | Catalog/source validation |
| `producer_v0_3_claims_catalog_expansion` | Claims catalog expansion |
| `producer_v0_3_bindings_catalog_expansion` | Bindings catalog expansion |
| `producer_v0_3_canonical_size` | Canonical normalized-size check |
| `producer_v0_3_internal_v0_1_schema` | Internal v0.1 schema parse |
| `producer_v0_3_recanonicalization` | Final canonicalization/size check |

Use one private shared parser pipeline with an optional private progress
callback that receives only these static labels. Set the label immediately
before its existing operation. The unchanged public
`parse_grounder_output_v0_3` calls that pipeline without progress; the new
runtime route supplies an assignment-only callback. Do not inspect or retain
wire values, exception text, field names, source/catalog data, or callback
arguments other than the closed labels. Keep operation order and existing
catch behavior.

The four frozen v0.1 producer checks and all semantic checks remain valid and
unchanged. The v0.1 and v0.2 runtime routes continue emitting exactly their
current checks/errors; only the explicit v0.3 route may emit the new labels.
No parser bytes/messages, audit, request budget, evidence, schema, receipt,
preparer, Builder, EI, prompt, or acceptance behavior changes.

## Target API and compatibility count

Pre-BUILD surface observed at freeze: `host_grounder_runtime` had 4 public top-level
functions and no explicit `__all__`; `host_grounder_evidence_catalog.__all__`
has 9 names; public `parse_grounder_output_v0_3` has 8 named parameters.
Keep all of these current signatures/exports intact. Target exactly one
additive public runtime function (subsequently implemented):

```text
run_host_grounder_same_run_evidence_catalog_v0_3(
    run_input, context, *, discovery_client, semantic_client, audit_holder,
    max_json_bytes, max_source_body_bytes, max_catalog_entries,
    max_catalog_bytes, max_catalog_paragraphs, host_context_preparer=None
)
```

Its 11 named parameters mirror v0.2; it selects the same preparer-backed,
v0.5-prompt path and differs only by opting into parser progress diagnostics.
The target runtime callable count is 5 (+1); catalog exports remain 9 and the
public parser remains at 8 parameters. These were frozen target counts;
the validated implementation counts are recorded below.

## Minimal later BUILD tests

- Inject one failure in each of the eight operation groups; assert exact
  closed v0.3 pair, unchanged error code/representation, and no later parser
  stage or semantic/preparer/Builder/EI call. Assert diagnostics contain no
  payload, exception detail, dynamic field name/value, or source information.
- Golden valid input: identical parsed value, normalized bytes, and audit
  behavior with and without the private callback.
- Existing v0.1/v0.2 routes: preserve signatures, bytes, errors and their
  original producer/semantic labels; constructor rejects every unlisted pair.
- Assert API counts/signatures above and that only the v0.3 route emits a
  fine-grained label. No live or source calls are part of these tests.

## Implemented validation

Actual post-BUILD surface: 5 public runtime entry functions; v0.2 and v0.3
have matching 11-parameter signatures; public parser remains at 8 parameters
and catalog exports at 9. Six new focused tests and 124 related Grounder tests
passed. Literal normalized-byte expectations, all eight injected failures,
route isolation and constructor closure are covered. Compileall, API checks,
Markdown links/fences and diff checks passed; independent final review passed.
No full-repository suite rerun or live/model/source call is claimed for this
diagnostic-only parser factoring.
