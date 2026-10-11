# Core Strategy Governance v0.1

Status: implemented and independently reviewed; local deployment verified.
User approval: 2026-10-11. This governs hypothetical research, not trading.

## Exact successor shape

Standard Research Profile v0.3 retains the v0.2 cash/sensitivity policy and
risk values unchanged and adds only this exact `strategy_governance` snapshot:

```json
{
  "version": "v0.1",
  "funding_rule": "OWN_CASH_PREMIUM; MARGIN_FINANCING_PROHIBITED",
  "lifecycle_intent": "CLOSE_OR_ABANDON_BEFORE_EXPIRY",
  "exercise_rule": "EXERCISE_TO_STOCK_PROHIBITED",
  "execution_enforcement": "NOT_ESTABLISHED",
  "automatic_exercise_protection": "NOT_ESTABLISHED"
}
```

These are explicit caller research assumptions. No component may present them
as broker controls, completed actions, executable closing, or protection from
automatic exercise. Passive inaction is not proven abandonment. Terminal
payoff geometry remains hypothetical; it is not an early-exit valuation.

## Cost and authority invariants

The four existing required cost components remain UNKNOWN with no numerical
bound: entry fees, strategy-dependent funding, exit and settlement. No tariff
package has been confirmed. Own cash does not establish zero opportunity or
funding cost; planned closing/abandonment does not establish a fill or zero
closing fees; prohibited stock conversion does not prove exercise prevention
or zero settlement cost. No loss/survival bound is upgraded by this policy.

Core formulas, DTOs, classification, numerical stress grid, provider authority
and optional historical evidence boundaries remain unchanged. All three
entries consume the same shared factory. No order/monitoring/exercise interface
is added.

## Compatibility and acceptance

Register exact v0.1, v0.2 and v0.3 snapshots. Preserve v0.1 historical custom
request compatibility and its original renderer cache. Preserve exact v0.2
factory semantics and renderer cache. Validate v0.2/v0.3 archives against their
own exact factories, not the newest profile. No database migration or historical
recomputation. Governance disclosure requires exact matching factory provenance;
a forged marker cannot upgrade a report.

Use explicit renderer-version mapping for each profile. v0.3 Chinese reporting
must distinguish approved intent from unestablished execution and automatic
exercise protection, and retain all unknown costs. Tests must cover all three
versions, cross-version rejection, unchanged v0.2 arithmetic/unknowns and
forged governance metadata. Independent review precedes commit.

## Validation

Focused profile/store/batch/direct/presentation tests: 90 passed (0.827s).
Related Core/application/presentation/HTTP tests: 89 passed (1.113s); these
sets overlap and are not 179 distinct tests. Compileall, Markdown links/fences
and diff checks passed. Proportional regression was used because Core arithmetic,
DTOs and market-data behavior did not change; the full 1,944-test pass belongs
to the preceding cash/sensitivity work, not this work unit.

Independent review found only a non-independent historical fixture; a literal
v0.2 snapshot and canonical JSON from committed `36db587` replaced it, and
targeted re-review passed. No production change was required for this finding.
The local workbench now serves v0.3 and all three configured executors; its
one historical Direct report remains readable with the unchanged SHA-256.
No research POST or quote request was used for deployment verification.

Measurement: first BUILD start 11:44:39 UTC; work/checks observed complete by
11:54:33 UTC, exact edit end and active coding duration unknown. Review 3m07s;
fixture repair/check window 22s. These partial measurements do not establish a
complete 70/30 phase allocation; permission waiting is not implementation time.
