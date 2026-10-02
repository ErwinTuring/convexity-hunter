# IREN Host binding-map trial — 2026-10-02

Separate one-shot exercise of [binding correspondence v0.1](host-grounder-binding-map-v0.1.md),
released as `1f51bdd43625b372ff085732a642c2bd91586c1c`. This is not replay of
the spent [corrected-profile attempt](standalone-iren-corrected-profile-trial-2026-10-02.md).
Use opt-in runtime v0.5, producer v0.6, semantic v0.6 and its Host-generated
ordered binding map. Same pinned SEC corpus, bounded identity, clarified F1/F2
questions, preparer, strict receipt/Builder/EI and temporal rules. No source
refetch, market data, Core, retry, raw retention or inferred economic policy.

Preserve the explicit resource profile: request discovery 80,000 / semantic
131,072 bytes, content/HTTP response 40,000, internal JSON 1,048,576,
string/array 8,000/64, source 20,000, catalog 64/32,768/128. DeepSeek Flash JSON
mode, thinking off; one reservation per role, 8,000/6,000 tokens, 45 seconds
each. Map bytes consume the request budget. All overflow/rejections fail closed.

Run ID: `iren-binding-map-20261002-b18ef3ac-8cd7-44f0-b962-48046fa9a718`.
Runner: `/private/tmp/iren-binding-map-20261002-b18ef3ac-8cd7-44f0-b962-48046fa9a718/runner.py`.
SHA-256: `223fca80c140e117466a16c5529733969147f7c956737e3e622be0643c753fe2`.
Directory/runner modes 0700/0600. Exclusive marker precedes invocation; only
sanitized aggregates may persist externally, 0600. External credentials stay
lazy and never enter model/context/output. No old artifact is modified.

Actual offline PASS: 7/9/11 runtime/catalog/signature checks and two targeted
map/strict-rejection controls. Immutable predecessor/helper pins retain prior
offline proof; those heavier controls were not rerun in this new preparation.
Zero live/source calls, credential reads or raw retention. Independent exact-hash
safety review and preregistration push must pass before Main live authorization.
Clean HEAD/main/origin equality, pinned-release ancestry and unchanged production
and source/helper hashes are required. No live outcome is claimed at registration.

Independent exact-hash safety review: PASS. Reviewer checked the narrow delta,
immutable pins, private modes, one-shot marker/gates and sanitized-only output
without executing fixtures, calls or reading raw content.

## Actual outcome — attempt spent

After preregistration `6203064` was pushed, Main authorized the exact frozen
runner once. Result: `STOPPED / SEMANTIC_CALL_FAILED`; failure stage/check null.
Discovery and semantic reservations were each one; source calls zero, no market
data, raw retention false, no receipt partition or EI result. No retry.

The producer structurally progressed to semantic invocation. Unvalidated census:
23,336 content bytes, 15 claims, one hypothesis, 36 bindings, four coverage
entries. The input hash remains
`0af5aa32b85ee1d196541abef94521d4a9f3231b6fac3df03c42239d911737d8`.
No semantic verdict reached the alignment check, so this is neither evidence
that the binding-map fix failed nor evidence that it passed live semantic
validation. Reservation counts must not be reported as confirmed successful
remote requests. The existing result does not establish timeout, transport,
request-size, response-size or truncation as the particular cause.

Independent factual review passed. Read-only transport inspection further
establishes that reservation occurs after request-size validation but before
credential resolution and HTTP invocation: the ordinary pre-invocation request
cap is not the cause of this post-reservation result. Other transport, response,
credential or unknown exceptions remain indistinguishable in the stored output.
Result SHA-256: `2369f1461187e7de6e5a5dc087b61ada3bf03ff8127ea0aa7ca3cc420175dd1a`;
marker SHA-256: `84777962888ac642e3d0e5371c9d37378320d95ceea5985326d59dcd248a8418`.
Both are mode 0600.

A bounded successor observer may record only exact-type, closed-allowlisted
`ModelTransportError.code` or a fixed unknown category, never error text, response
body, headers or credentials. It must forward arguments/completion/config/budget
unchanged and rethrow the original exception. Synthetic transparency controls
and a separate one-shot safety/preregistration gate precede any live invocation.
This is diagnosis, not production acceptance or permission for budget relaxation.

Marker/result remain in the registered private directory; the protocol is spent.
Do not increase budgets, change models or repeat blindly. The next bounded work
is closed-code semantic-call diagnosis, without raw payload/exception text,
credentials, source refresh or market data. No general product success claim.
