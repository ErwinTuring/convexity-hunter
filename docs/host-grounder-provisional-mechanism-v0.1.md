# Provisional mechanism assessment v0.1

Status: FROZEN / INDEPENDENT CONTRACT REVIEW PASS / NOT IMPLEMENTED.

## Existing meaning, narrow correction

The [EI acceptance contract](event-intelligence-acceptance-contract.md) permits
interpretations with source-backed factual dependencies. The [Host semantic
contract](host-grounder-semantic-validation-v0.1.md) explicitly says market
impact remains a hypothesis, not a source-established outcome. Producer v0.9
already asks for labeled provisional explanations. Verifier v0.7 instead
supplies general support instructions without explicit role-specific criteria.
The latest TMQ refusal mentions absent direction/magnitude/window; that is a
model rationale, not a new mandatory condition or proof the hypothesis is valid.

Introduce only verifier prompt v0.8, retaining v0.7 unchanged. Append criteria:

- Observed facts require faithful original-source wording, attribution, actor,
  polarity, time role and scope; an interpretation cannot authorize a fact.
- An interpretation/provisional hypothesis is assessed as a conditional,
  source-grounded explanation, not as a source-reported market prediction.
  Require concrete supported premises, an explicit transmission link to the
  identified entity/exposure, preserved dependencies, uncertainty and inspected
  counterevidence. A generic possibility or merely having an event is not a
  mechanism. Missing economic/entity dependence remains unresolved.
- A source need not itself state a future security-return direction,
  numerical magnitude, probability or precise impact end to support such a
  qualified explanation. This supplies none of those missing values. A claimed
  direction/mode still needs its own defensible support; do not fill it by
  default. Unsupported identity, dates/windows and reassessment stay missing.
- For a `hypothesis`-role field binding, assess whether the exact bound paragraph
  grounds the stated conditional link in its declared claim context; do not
  require its inference wording to be a literal source quotation. Exact catalog
  ID/paragraph/span correspondence remains mandatory. Dependency declarations
  cannot rescue an unrelated paragraph or replace missing premises.
- `supported` remains fallible evidence support, never causal proof, EI
  acceptance, opportunity, recommendation or positive expected return. Keep
  contradicted/unresolved outcomes and legitimate empty output.

## Wiring and compatibility

Only the normal producer-v0.9 route selects verifier v0.8; retain its producer,
public factory/API, wire/receipt schemas, request limits, model and repair
budget. Older routes keep their exact prompt selections. Add v0.8 to the closed
catalog audit version set and Host archive validation, permitting it only with
producer v0.9; old v0.7 archives remain readable. Do not rewrite old metadata,
expand general version acceptance or change SQLite schema. World reuses the
same normal grounder; Direct v0.4 and EI/Core stay unchanged.

Do not suppress or reinterpret existing receipt rejection strings to obtain
acceptance. An unresolved verdict may have no refs; a resulting supporting-
source failure is not automatically an independent original cause. Without
the original ref list, the latest TMQ sidecar cannot settle that attribution.

## Validation and one normal operation

First independently review this clarification against existing contracts.
Then test actual normal selection/new audit version, preserved v0.7, exact
bindings and wrong-source/dependency rejection, unresolved/contradicted refusal,
old/new archive recovery, and lawful fact→interpretation→hypothesis→EI wiring.
Fixtures prove code/contract behavior, not model judgment quality. Keep tests
small; no generic diagnostic platform, old A recovery or A/B campaign.

After review and relevant regression pass, one new normal Event operation may
use at most two Tavily requests/three credit reservations and two model
requests per role, with existing admission and Core bounds. Freeze input,
evaluation date and a new once guard before calls; do not replay the spent
TMQ guard, retry for positivity, inject a context or reuse an accepted result.
A lawful submission immediately enters EI and accepted branches the shared
Core. Nonacceptance is evidence, not permission to weaken gates. Keep minimal
original per-item reasons privately, no full raw response or credentials.
