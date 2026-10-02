# Host semantic binding correspondence v0.1

Status: **IMPLEMENTED — independent contract and final code review PASS.**
Implementation was absent at freeze. The additive route is now implemented;
this status does not claim a new real product acceptance.

The [corrected-profile trial](standalone-iren-corrected-profile-trial-2026-10-02.md)
reached semantic validation and failed binding alignment. Its exact subcause is
unknown. Independently, code inspection proves the old verifier prompt requests
an envelope evidence ID that normalization has expanded away. The full catalog
allows reconstruction, but deterministic Host correspondence should not require
model reconstruction. This remedy does not assert the spent trial's cause.

## Minimal additive shape

Add opt-in `run_host_grounder_same_run_evidence_catalog_v0_5`, with the same
11-parameter signature, result, required preparer and fine diagnostics as v0.4.
Producer remains v0.6. New route alone selects semantic prompt v0.6 and adds
`producer_binding_evidence_map` to the semantic input object:

```json
[{"index": 0, "evidence_id": "FORMAT_ONLY_ID"}]
```

This example is shape only, not a source fact. Host enumerates exactly the
already-extracted IDs after successful producer validation, preserving binding
order and repeated IDs; empty bindings produce an empty map. No new model
output field. The normalized envelope bytes/hash remain untouched.

Semantic v0.6 must declare that the map establishes lexical correspondence only,
not truth, support, entailment, authority or a required supported verdict. For a
supported binding, references must include its mapped ID, as the existing parser
already requires. Independent contradicted/unresolved assessment remains legal.
Wrong valid catalog IDs, invalid indices/counts and malformed output continue
to fail closed. No coercion, repair, omitted record or weaker acceptance.

All existing routes retain their exact prompts and semantic framing. Add private
semantic-version plumbing defaulting to v0.5, with a closed v0.5/v0.6 allowlist
and selected/expected equality in audit finalization. Populate the existing audit
and receipt `validator_version` fields with the actually selected version. No
new audit key/schema or public parser/receipt API. Unknown or mismatched versions
fail closed. Runtime count is now 7 (6 at freeze); catalog exports remain 9.

No request/output/resource default changes. Map bytes count toward the explicit
128 KiB semantic request ceiling, checked before invocation; overflow remains
a stop, not truncation or automatic budget increase. No additional calls,
raw retention, data source, model, economic policy or Core change.

## BUILD/release checks

Literal legacy prompt/framing compatibility; exact map order, repeated/empty IDs;
new semantic header and prompt obligations; selected audit/receipt version
agreement and mismatch/unknown rejection; required preparer; unchanged 11
parameters, 7/9 target counts; supported wrong-ID rejection; request overflow
before invocation. Run focused and relevant regression, compileall/diff/docs
checks; broader regression as justified by the small changed dispatch/audit
surface. Independent final review before commit. No live trial during BUILD.

BUILD validation: 23 catalog tests, 28 context-preparation tests and the complete
133-test Grounder-focused suite passed on the corrected indexed-map prompt.
Private-cache compileall and diff checks passed. This small dispatch/framing
change did not rerun the earlier 1,650-test whole-repository suite; that PASS
belongs to the preceding typed-entity unit. Final independent code review is
PASS. It verified the corrected prompt, literal legacy compatibility, map and
version tests, strict wrong-ID rejection and independent request limits.
No model/source/live calls were made during this BUILD.
