# Futu Browser-to-Direct-Entry Real Exercise

## Scope

On 2026-08-20, one repository-external script reconstructed the accepted AAPL
bidirectional-distribution-expansion path, retrieved current Futu chain
evidence, and recreated the bounded Exact Contract Browser. A human explicitly
selected one listed Long Straddle from the 15 neutral Browser pairs presented
on the prior step:

```text
expiration: 2026-11-20
strike: 295
Call: US.AAPL261120C295000
Put:  US.AAPL261120P295000
quantity: 1 per leg
assumed portfolio value: USD 10,000
expected holding period: 30 calendar days
```

The strike was the median of the displayed 15-pair navigation slice. That fact
is not an ATM, near-ATM, Delta, candidate, cheapness, liquidity,
recommendation, or preference claim. The portfolio value and holding period
were explicit user-supplied MVP exercise assumptions, not optimized values,
forecasts, or recommendations.

## Exact verification path

The exercise ran only the implemented path:

```text
accepted AAPL hypothesis
→ current bounded discovery request
→ real Futu chain evidence
→ Exact Contract Browser
→ explicit human selection
→ Futu exact-selection verification bridge
→ provider-neutral Direct Entry exact-contract gate
→ partial CandidateResearchRecord
→ DATA_INSUFFICIENT screening
→ deterministic Chinese report
```

Both selected Browser rows were retained by identity. The bridge called the
existing exact Futu verifier for both legs and confirmed provider identifiers,
expiration, strike, Call/Put, provider `MONTH`, provider `STANDARD`, validity,
and provider multiplier 100. It substituted no contract. The two resulting
provider-neutral references remained `INCOMPLETE` rather than inventing exact
deliverable or settlement semantics.

## Sanitized result

```text
provider exact verifications: 2
bridge Direct Entry exact verification: PASS
service Direct Entry exact verification: PASS
research-readiness verification: absent
candidate state: DATA_INSUFFICIENT
screening state: DATA_INSUFFICIENT
screening reasons:
  - missing_costs
  - missing_liquidity
  - missing_volatility_environment
  - missing_structure_expiration_tail_slice
  - missing_target_move_scenario
  - missing_volatility_crush_scenario
position-management plan: absent
Chinese report: nonempty, 2,992 characters
report SHA-256: 25635e0e769a6b8f4a319ee77ccfb5aeaeb3506a784ddb189858fbeca6ffd524
raw provider payload persisted: NO
contract substitution: NO
BBO/history/account/trading calls: NO
```

The explicit missing-data disclosure retained the absence of authoritative
current quote time/session semantics, complete costs and liquidity, volatility
environment, tail-relative pricing, scenario valuation, expiration thresholds,
and affordability evidence. No provider-native field was promoted to a
provider-neutral observation merely to advance the state.

## Conclusion

The first real human-selected Browser-to-Direct-Entry partial loop is proven.
This does not authorize automatic Candidate Generation, default selection,
ranking, ATM/Delta inference, or weaker research evidence. Complete research
readiness remains blocked by the already-recorded authoritative evidence gaps;
the honest partial research path remains usable as `DATA_INSUFFICIENT`.

This historical exercise predates the Discovery Entry temporal-applicability
gate. Its accepted hypothesis ended in 2025 and therefore cannot be replayed as
current discovery for a 2026 evaluation date after that gate. The exercise
remains evidence of downstream Browser-to-report mechanics only. The next real
product exercise must begin from a current or future event with a non-expired
explicit expected window.
