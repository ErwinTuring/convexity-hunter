# Futu Option-Chain Discovery Real Exercise

## Scope

On 2026-08-19, a repository-external script reconstructed the already accepted
AAPL SEC-filing hypothesis, created one exact `OptionChainDiscoveryRequest`,
and exercised the bounded Futu option-chain discovery evidence boundary against
the user's already-authenticated local OpenD.

The script made only expiration and option-chain calls. It emitted sanitized
aggregate JSON after closing the quote context. It persisted no raw provider
payload, printed no provider contract identifiers or strikes, read no
credentials, and made no snapshot, BBO, history, account, or trading call.

## Sanitized result

```text
assessment status: accepted
underlying: AAPL
inclusive expiration interval: 2026-09-18 through 2027-01-16
request identity retained: YES
expiration classifications retained: 7
provider MONTH expirations: 5
other provider expiration cycles: 2
contract rows retained: 880
calls: 440
puts: 440
provider-classified ELIGIBLE rows: 880
NON_MONTHLY rows returned by monthly-chain calls: 0
NON_STANDARD rows: 0
SUSPENDED rows: 0
all receipt timestamps aware UTC: YES
raw payload persisted: NO
structure selected or generated: NO
```

The counts describe this single provider response at exercise time and are not
portable product constants.

## Evidence boundary and next gate

The exercise proves the implemented path:

```text
accepted source-backed hypothesis
→ exact discovery handoff
→ bounded maturity request
→ real Futu expiration and chain evidence
→ deterministic provider-classified row applicability
```

It does not prove exact deliverables, quote freshness, Delta methodology, an
ATM reference, research readiness, or investment attractiveness. It does not
authorize automatic contract selection or structure generation.

For the accepted bidirectional hypothesis, the current product policy requires
an ATM or near-ATM Long Straddle. Futu's currently accepted evidence boundary
does not provide an authoritative fresh underlying quote or an authorized ATM
reference. Directional modes likewise lack authoritative Delta methodology and
observation semantics. Therefore the next implementation step is not
mechanically determined.

A product/architecture decision is required before generation work: either
retain the strict mode-based generation gate until authoritative inputs exist,
or explicitly define a bounded manual-selection handoff from an unranked
provider-classified catalog. No such choice is made by this exercise.
