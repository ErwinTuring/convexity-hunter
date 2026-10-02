# Host Grounder Producer Diagnostics v0.1

Status: **CONTRACT FROZEN — IMPLEMENTED AND INDEPENDENTLY REVIEWED.**
Independent contract and code reviews passed. This is a diagnostic-only extension for
producer normalization in the opt-in catalog runtime v0.2. It authorizes only
the bounded offline BUILD below, not a live run.

## Contract proposal

The existing catch maps four operations to
`HostGrounderRuntimeError("PRODUCER_ENVELOPE_INVALID")`: producer parsing and
normalization, exact request/stage comparison, ordered-coverage validation,
and final wire binding-evidence extraction. Preserve that error code and expose
only this closed operation pair in the v0.2 route:

| `failure_stage` | `failure_check` | Operation |
| --- | --- | --- |
| `producer_envelope_normalization` | `producer_wire_normalization` | `parse_grounder_output_v0_3` and normalized-byte decoding |
| `producer_envelope_normalization` | `producer_run_stage_binding` | `request_id` / `stage` comparison |
| `producer_envelope_normalization` | `producer_coverage_order` | `validate_ordered_coverage_ids` |
| `producer_envelope_normalization` | `producer_binding_extraction` | Decode original producer wire and extract ordered binding evidence IDs |

Use one private local check string to set each static check immediately before
its existing operation. Keep the catch, order, and fail-closed result; do not
add retries or payload/exception inspection. Extend constructor validation so
the new stage is legal only with code `PRODUCER_ENVELOPE_INVALID` and one of
these four checks. Preserve all existing semantic stage/check combinations,
`.code`, `.args`, `str`, `repr`, and suppressed chaining. Legacy and
catalog-v0.1 errors retain `failure_stage=None` and `failure_check=None`.

## Compatibility boundary

No wire, parser behavior/bytes, runtime signature, audit, call budget, evidence,
schema, receipt, Builder, or EI gate changes. No exception text, payload,
identifier, source/catalog content, field name, or field value is disclosed.
The v0.5 prompt's mandatory bindings and the parser's acceptance of
structurally valid partial evidence are not a demonstrated contradiction:
prompt instructions do not grant support, parser acceptance does not imply
Builder projectability, and Builder remains fail-closed. Do not tune the prompt
or relax/strengthen any acceptance rule. The spent IREN run remains
`PRODUCER_ENVELOPE_INVALID`; this proposal cannot recover its exact check.

## Minimal offline test matrix for later authorized BUILD

- Inject failure at each of the four operation groups: preserve the error code
  and representation; assert the matching closed stage/check; prove no later
  semantic, preparer, Builder, or EI call occurs.
- Valid catalog-v0.2 input: identical normalized bytes and audit behavior.
- Invalid legacy/catalog-v0.1 input: existing error behavior and null
  stage/check.
- Preserve existing semantic diagnostics and reject invalid stage/check pairs;
  assert no payload or exception detail leaks.

No retained live payloads, model/source calls, retries, or spent-protocol
reopening are part of this proposal.

## Implementation evidence

The constructor accepts only the closed producer pairs with the unchanged
`PRODUCER_ENVELOPE_INVALID` code. One local check string tracks existing
operations; the preparer-backed v0.2 route alone exposes these diagnostics.
Legacy/catalog-v0.1 behavior, semantic diagnostics, normalized bytes, audit
behavior, runtime signatures and exports remain unchanged.

Actual validation: 61 unittest tests passed (context preparation 24, runtime
25, evidence catalog 12), relevant compileall, API/signature comparison,
Markdown links/fences and diff check passed. Independent final code review
passed. The full suite was not rerun for this diagnostic-only extension;
earlier full-suite results are historical, not a new regression claim.
No live model or source request was made during this BUILD.
