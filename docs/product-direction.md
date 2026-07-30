# Convexity Hunter Product Direction

This document is the canonical product direction after Milestone 3. It defines
the active product objective and roadmap without changing the completed
Milestone 1–4 implementation.

## 1. Product objective

Convexity Hunter starts from changes in the world, identifies events that may
alter future return distributions, identifies potentially affected
underlyings, uses real option-chain data to construct actual Long Option
Position candidates, lets the user select one exact option structure, and then
uses auditable market evidence to determine whether its positive convexity may
be insufficiently priced and whether its maximum loss fits the user's
explicitly declared risk assumptions.

The system identifies structures worthy of further investigation. It does not
prove that an opportunity exists, recommend a trade, or execute one. The final
unit of research is one exact option structure, not a generic asset or a
multi-position optimized portfolio.

## 2. Supported research unit and scope

`Long Option Position`, `option long position`, `期权多头仓位`, and
`买入期权结构` describe position direction. Do not use “长期权” as a synonym:
it may be confused with a Long-Term Option or LEAPS.

The active MVP supports exactly:

- Long Call;
- Long Put; and
- Long Straddle: one long call and one long put with the same underlying,
  strike, and expiration.

Each selected structure records the underlying, structure type, side of every
leg, strike, expiration, quantity, and contract multiplier. Candidate
discovery uses one standard structure unit unless the user supplies another
quantity.

The MVP excludes short options, option selling, spreads, multi-expiration
structures, exotics, 0DTE, Weeklies, portfolio optimization, automatic
execution, probability forecasts, trade recommendations, and calculation of
an optimal contract count.

## 3. Two entry paths

Discovery entry:

```text
world events
    -> Event Intelligence
    -> potentially affected underlyings
    -> distribution-change hypotheses
    -> real option-chain retrieval
    -> actual eligible option structures
    -> user selects one exact structure
    -> Convexity Engine research
```

Direct user entry:

```text
user supplies an option structure to investigate
    -> resolve and validate the real listed contract
    -> apply the same market-data, eligibility, evidence, and scope checks
    -> Convexity Engine research
```

Direct entry does not require an Event Intelligence hypothesis. It never
bypasses real contract existence, option-chain verification, supported
structure grammar, DTE policy, quote and reference-data validation,
market-data provenance, or calculation lineage. An incomplete description may
be resolved against the actual chain, but the system must never invent a
contract. Both paths converge on one verified exact `OptionStructure`.

## 4. Dual-engine architecture

Event Intelligence is the hypothesis engine. It identifies events,
potentially affected underlyings, impact paths, distribution-change
hypotheses, expected event windows, supporting and contradictory sources, and
uncertainty.

Event-to-underlying mapping is Skill-led. Convexity Hunter owns the standard
accepted result and minimum audit boundary: underlying identity resolution;
event and observation time; source retention; fact-versus-inference
separation; disclosed impact path, distribution hypothesis, and event window;
uncertainty and conflicts; Skill identity and version; and incomplete-result
handling. This is an acceptance interface, not a second mapping algorithm. Its
detailed contract requires separate future design after Skill research.

A market-data and deterministic-rules component retrieves the real option
chain, confirms listed contracts, applies maturity and future strike-or-Delta
policies, constructs exact supported candidates, verifies required quote, IV,
Greeks, volume, open-interest, and reference evidence, and rejects nonexistent
or invalid structures. Language-model reasoning cannot replace the chain.

The Convexity Engine researches the exact selected structure using auditable
numerical market evidence. It does not discover contracts, make the user's
selection, or decide a trade.

## 5. Skill reuse and adapter strategy

Event Intelligence should preferentially reuse mature Skills to reduce
implementation cost and improve delivery speed. A third-party Skill may,
however, satisfy only part of the product contract.

The boundary has three layers:

1. Skill-native output is fixed by the Skill and is not arbitrarily changed by
   Convexity Hunter.
2. Adapter and Skill composition provide thin conversion, enrichment, or
   combination where necessary.
3. Convexity Hunter standard accepted input is the normalized
   event-to-underlying hypothesis contract required by the product.

A mature Skill may be used directly, wrapped by a thin adapter, combined with
another Skill, rejected as insufficient, or supplemented by narrowly scoped
internal development. Capability research must precede that decision.

AI, search, and knowledge Skills may provide event identity, summary,
observation time, source references, potentially affected underlying, impact
path, distribution-change hypothesis, expected event window, supporting and
contradictory evidence, uncertainties, and Skill identity and version. These
are hypotheses and interpreted evidence. They may not invent option prices,
strikes, expirations, listed contracts, implied volatility, Greeks, historical
observations, scenario values, or probabilities.

## 6. Candidate qualification and layered selection

Eligibility, not arbitrary absolute counts, controls candidate inclusion. An
underlying may enter structure generation only when the future accepted
contract establishes a supported US-listed equity or ETF identity, a specific
event-impact path and future distribution-change hypothesis, source-backed
mapping, a usable event window, an eligible listed option market, and
resolvable identity and chronology.

A structure may enter only when the contract exists, the structure is
supported, maturity is eligible, required quote and reference evidence is
available, and the structure is compatible with the declared distribution
hypothesis.

Information volume is controlled through layered interaction:

```text
event
    -> eligible affected underlyings
    -> user opens or selects one underlying
    -> eligible exact option structures
    -> user selects one exact structure
```

The system does not rank structures by investment attractiveness. Stable
presentation ordering is permitted but is not a recommendation.

## 7. Maturity policy

The initial versioned MVP policy permits standard monthly options only:

- hard lower bound: 30 calendar DTE;
- non-core short range: 30–59 calendar DTE;
- core hunting range: 60–120 calendar DTE;
- non-core long range: 121–150 calendar DTE;
- hard upper bound: 150 calendar DTE; and
- expiration date must be at least the expected event-window end date plus 30
  calendar days.

0DTE and Weeklies are excluded. The event buffer is an initial policy
assumption. The DTE ranges are Convexity Hunter product choices, not a fixed
universal Taleb rule. They must be versioned and may change through evidence
and backtesting. The exact definition of “standard monthly option” remains for
the future structure-generation contract.

### 7.1 Mode-based Strike and Delta generation

Discovery generation uses the declared distribution-change mode rather than
one universal Strike or Delta range:

1. **Extreme-tail mode** applies to a specific one-sided extreme downside or
   upside hypothesis. Signed option Delta is preserved as evidence; absolute
   Delta qualifies the range. The initial primary tier is
   `0.05 <= abs(delta) <= 0.10`. The fallback tier is
   `0.10 < abs(delta) <= 0.15` and is used only when the primary tier cannot
   provide an eligible real listed contract with sufficient required market
   evidence. The exploratory far-tail tier is
   `0.02 <= abs(delta) < 0.05`; it is not generated by default and requires a
   real listed contract, valid two-sided quote, usable liquidity evidence,
   available IV and reference evidence, calculable total entry cost, and
   responsible scenario valuation. Absolute Delta above 0.15 is outside this
   default grammar, not globally prohibited.
2. **Event-directional convexity mode** applies when an event creates a
   meaningful directional tail hypothesis that need not be a systemic or
   extreme-market crash. Representative targets remain approximately 10
   Delta—a farther tail with lower absolute premium, a potentially higher
   value multiple, and a larger required move—and approximately 25 Delta—a
   less remote event-sensitive structure with usually higher absolute cost
   that may respond earlier to a material event move. Neither target is
   preferred or ranked. A 25 Delta structure remains a possible candidate,
   tail-pricing comparison point, and wing-curvature evidence anchor.
3. **Bidirectional distribution-expansion mode** applies when direction is
   unresolved but the future return distribution may widen. The active MVP
   uses an ATM or near-ATM Long Straddle because it does not support Long
   Strangle.

Future deterministic generation contracts must define the Delta convention,
nearest-eligible-Delta resolution, tie handling, expiration interaction,
mode-specific quote and liquidity qualification, and the exact disclosed ATM
reference. This policy does not freeze those implementation choices, and
structure generation is not yet implemented.

The ranges govern discovery generation. A supported real structure supplied
through direct user entry is not rejected solely for falling outside them. It
still must pass real-contract verification, supported Long Option Position
grammar, DTE policy, quote and reference validation, market-data provenance,
calculation lineage, liquidity and cost analysis, and Convexity Engine
research. The report may disclose that it does not match a default discovery
mode.

Delta is not a fixed percentage distance from spot. It depends on disclosed
inputs and methodology, including underlying price, strike, remaining
maturity, implied volatility, rates, dividends, surface shape, and pricing
convention. Every generated structure must disclose its actual strike
distance separately.

Low dollar premium is not relatively cheap tail pricing. Deep OTM options may
carry expensive tail IV, wide spreads, poor liquidity, or model-sensitive
values. Initial far-OTM Gamma is commonly low and can increase as the option
moves toward ATM; tail-event value may reflect price movement, IV repricing,
skew or surface repricing, and changing Greeks. No universal claim of high
initial Gamma or maximum Vega applies, and Vanna or Volga are not required MVP
fields.

## 8. Three-layer Convexity Engine

Layer 1 asks whether the overall option-pricing environment is relatively
quiet or expensive. It includes ATM IV percentile, ATM IV relative to its
historical median, IV term structure, and the matched-horizon
implied-versus-realized volatility gap.

Layer 2 asks which tail, if any, appears relatively cheap against ATM and its
own history. It includes 25-delta put IV minus ATM IV, 25-delta call IV minus
ATM IV, 10-delta versus 25-delta wing curvature, current skew percentile, and
skew term structure.

Layer 3 asks whether the exact structure is a bearable and sufficiently
nonlinear way to own the hypothesized convexity after costs. It includes the
real price, spread, commissions and fees, total entry cost, maximum loss,
Theta, raw total-position Gamma, local Gamma-cost relationship,
repeated-failure cost, scenario values, expiration value thresholds,
portfolio-relative loss, and risk-budget assessment.

Positive convexity does not establish cheapness. A Long Option Position can be
positively convex yet too expensive, illiquid, rapidly decaying, or
inconsistent with the hypothesis. Detailed numerical contracts live in
[the market-data specification](market-data-contracts.md) and deterministic
decision rules in [the screening policy](screening-policy.md).

## 9. Expiration payoff-threshold evidence

The implemented deterministic expiration transformation uses:

```text
expiration position-value multiple =
    expiration gross position value / total entry cost
```

The exact ordered target set is 1x, 2x, 5x, and 10x. At 1x, expiration gross
position value equals total entry cost: break-even before any separately
disclosed expiration exit cost. Total entry cost includes total-position
midpoint premium, one-way entry spread cost, commissions, and fees. Exit cost
is excluded from the threshold equation.

The transformation supports Long Call, Long Put, and the current same-strike,
same-expiration, same-quantity, same-multiplier Long Straddle. It returns the
structure-appropriate single or double payoff branches and explicitly
represents a lower-side solution that is unavailable on the nonnegative
underlying-price domain.

Every available threshold includes a signed absolute USD-per-share move and a
signed relative move from the reviewed base underlying price. A percentage is
a later presentation derivation from the relative move. Side identifies the
payoff branch and does not necessarily equal the sign of the move from the
current base price. “Exact” means mathematically exact rational evidence, not
a rounded `Decimal` or float approximation.

The implemented transformation produces expiration payoff-threshold evidence
only. It
calculates no probability, expected return, direction forecast,
recommendation, position sizing, automatic exit advice, or screening or
report consequence. Candidate assembly, screening and reporting integration,
position-management integration, and services remain later work. The complete
public artifact, exact mathematics, validation, lineage, and export contract
is frozen in
[Milestone 4 of the market-data specification](market-data-contracts.md#1323-milestone-4-deterministic-expiration-payoff-threshold-evidence).

## 10. Non-expiration scenarios

Non-expiration scenario value asks what the structure might be worth at an
intermediate valuation time if underlying price, implied volatility, remaining
time, rates, dividends, and the volatility surface change. It captures price
movement, IV repricing, remaining time value, Theta decay, IV-collapse risk,
and potential pre-expiration liquidation value.

Expiration thresholds show terminal payoff shape and tail-value steepness;
non-expiration scenarios show possible value while time and volatility value
remain. The repository currently validates and consumes authoritative
non-expiration scenario-pricing evidence but does not produce those prices.
A future milestone must select and disclose an external provider, an internal
pricing model, or both.

The existing general v0.1 scenario grid remains the current implemented
baseline. Future extreme-tail generation must add directionally aligned
event-level, severe, and extreme-tail stress rather than relying only on
ordinary ±5% or ±10% moves. Exact shocks must be versioned and may differ for
an index, ETF, lower- or higher-volatility equity, or event type; there is no
universal ±30% scenario.

Every IV shock must disclose base IV, shocked IV, and whether the change is a
relative percentage or absolute volatility-point change. Current v0.1
proportional IV scenarios retain their implemented semantics. Future
mode-specific contracts may add disclosed surface and skew changes.

A large value multiple under an extreme scenario is important evidence, but
no single multiple—including 50x—automatically determines `Investigate`.
Screening continues to use the complete applicable evidence boundary,
including volatility environment, tail-relative pricing, liquidity, cost,
affordability or `Data insufficient`, scenario coverage, expiration
thresholds, and evidence quality.

## 11. Risk-budget assumptions

Discovery and generation do not require portfolio value or a risk budget.
After exact-structure selection, research may accept explicit caller
assumptions equivalent to assumed portfolio value, maximum single-structure
loss fraction, repeated-bet count, maximum repeated-loss fraction, and
risk-budget methodology.

The system may calculate:

```text
single-loss fraction = total entry cost / assumed portfolio value
repeated-loss fraction =
    total entry cost * repeated-bet count / assumed portfolio value
```

It imposes no universal portfolio-risk percentage. If portfolio value or risk
budget is absent, report absolute entry cost, absolute maximum loss, and
absolute repeated-failure costs; do not claim bearability; and mark
affordability `Data insufficient`.

Single-structure maximum-loss fraction, repeated-failure cost, and a possible
future annual convexity budget are distinct. The product imposes no universal
1%–1.5% annual tail-protection cost. Any annual budget must be explicitly
supplied by the caller or user; its contract remains a future design question,
not a frozen record field or public API.

## 12. First-report position-management conditions

The product does not monitor positions, schedule tasks, send alerts or
notifications, or automate exits. The first report states limitations and
human-readable conditions for later judgment:

- monetization conditions: for example, executable net liquidation value at a
  disclosed 2x, 5x, or 10x cost multiple; disclosed ATM IV or skew thresholds;
  the event becoming public; disappearance of underpricing evidence; or
  growing Theta/IV-collapse dominance;
- reassessment conditions: for example, a disclosed event-window shift, loss
  of the 30-day buffer, remaining DTE reaching 30 days, a disclosed spread
  threshold, stale or missing evidence, contract adjustment, or a material
  impact-path change; and
- exit conditions: for example, event-window expiry without the hypothesized
  change, cancellation or definitive contrary resolution, a confirmed
  exemption, invalidated impact path, inability to cover the revised event
  window and buffer, breach of the user's risk boundary, liquidity below
  disclosed limits, or data loss that prevents responsible evaluation.

Conditions should be quantitative where evidence permits. There is no
universal automatic 2x take-profit rule or option-price drawdown stop. The
active report says “consider monetization,” “consider reassessment,” or
“consider exit”; these are not mandatory trade commands.

A future `PositionManagementPlan`-like immutable record is a design direction,
not a frozen class, module, or signature. Preflight must decide its record
boundary; deterministic versus Event Intelligence, caller, human, or AI
inputs; threshold derivation and disclosure; and integration with research and
reporting.

## 13. Chinese report and simplified overview

The active product flow produces a Chinese report only. The implemented
English renderer remains for compatibility and possible future reuse, but
English is inactive. Reactivation requires a separately accepted product
decision; completed bilingual implementation remains a historical fact.

The first report section is a short, ordinary-Chinese overview for users with
little option experience:

1. the exact underlying and structure in beginner-readable language;
2. the final research disposition—Investigate, Watch, Reject, or Data
   insufficient in plain Chinese—and an explicit reminder that it is research
   priority, not a buy/sell recommendation;
3. a few decisive supporting and caution reasons;
4. the main uncertainty, missing evidence, false-positive risk, or
   human-review question; and
5. concise future monetization, reassessment, and exit conditions.

Necessary option terms are explained briefly. The overview contains no
unexplained jargon, long methodology, full metric/provenance tables,
uncalculated probabilities, or implied trade recommendation. Detailed
provenance, lineage, metrics, costs, risk calculations, thresholds, scenarios,
evidence, falsification, methodologies, limitations, and review questions
remain below. If supplied `CandidateResearchRecord` state differs from the
deterministic `ScreeningDecision`, one short sentence surfaces the
disagreement; details retain both exact states and reason codes.

“最终建议” means research disposition. Acceptable wording includes
“最终研究结论”, “是否值得进一步研究”, “建议继续调查”, “建议观察”,
“建议暂不继续”, and “数据不足，无法负责地判断”. It must not become a
buy/sell instruction, return claim, or probability claim.

## 14. Completed Milestones 1–3

Milestone 1 implemented `CandidateResearchRecord`, evidence classification,
supporting and contradictory evidence, falsification, false-positive reasons,
human-review questions, deterministic report rendering, and a plain-language
overview before technical detail. Bilingual rendering is a completed
historical fact.

Milestone 2 implemented `ScreeningPolicy`, `ScreeningDecision`, Reject, Watch,
Investigate, Data insufficient, canonical reason codes, deterministic
precedence, and report integration that keeps research and proposed states
separate.

Milestone 3 completed at commit
`86aee1dfa13cae0c865d8f24aa08754934abd540` (`Implement hybrid scenario
valuation transformation`). It implemented provider-neutral market-data
contracts, provenance and normalization, freshness, correction selection,
relationship coherence, cross-observation selection, historical-series
assessment, calculation lineage, structure liquidity and costs, historical
realized volatility, volatility environment, tail relative pricing, a
scenario-pricing evidence contract, and hybrid non-expiration/expiration
scenario valuation.

## 15. Current gaps

Convexity Hunter has largely completed the auditable numerical and evidence
foundation for researching one already-specified option structure. It has not
yet completed the active-discovery front end, real option-structure
generation, production candidate assembly, position-management-plan
integration, non-expiration pricing production, or the complete application
flow. Milestone 4 implements deterministic exact-rational expiration
1x/2x/5x/10x payoff-threshold evidence.

Project claims must distinguish implemented capability, implemented record or
contract, transformation requiring caller orchestration, synthetic-only
integration, and not-yet-implemented work. A domain record alone is not a
complete application workflow.

## 16. Corrected roadmap

1. Documentation alignment: persist this post-Milestone-3 consensus without a
   new numerical capability.
2. Completed Milestone 4: deterministic exact-rational Expiration
   Payoff-Threshold Evidence for exact 1x, 2x, 5x, and 10x thresholds.
3. Complete the single-structure research engine, subject to separate
   preflights: explicit risk-budget and affordability contract;
   reviewed-artifact-to-`CandidateResearchRecord` assembly;
   position-management-plan contract; screening and Chinese-report integration;
   and one deterministic offline single-structure service.
4. Produce non-expiration scenario pricing using a disclosed provider,
   internal model, or both.
5. Research mature Skill capabilities, native interfaces, direct reuse,
   adapter and composition requirements, and narrow internal gaps.
6. Implement Event Intelligence: retrieval, clustering and deduplication,
   timing, distribution hypothesis, supporting and contradictory sources,
   event window, and uncertainty.
7. Implement the Skill-led event-to-underlying accepted contract and audit
   boundary.
8. Implement real option-chain access, contract verification, maturity and the
   accepted mode-based Strike/Delta policy, supported structure generation,
   and layered selection.
9. Connect the complete active-discovery flow from Event Intelligence through
   exact user selection, Convexity Engine, research record, screening,
   position-management plan, and Chinese report. Direct entry converges on
   the same engine.

## 17. Locked principles

- Events create hypotheses; numerical market evidence tests pricing.
- AI explains and structures research but never invents numerical evidence or
  makes the trade decision.
- The user chooses one verified exact structure.
- Positive convexity is not proof of cheapness.
- Risk bearability depends on explicit user assumptions.
- Candidate qualification is rule-based and selection is layered, not
  arbitrarily capped or automatically ranked.
- Strike and Delta discovery generation is mode-based, not universal; 25 Delta
  is not globally rejected and direct entry is not bounded by discovery-mode
  defaults alone.
- Low premium does not establish cheapness, no single scenario multiple
  determines `Investigate`, and no universal annual convexity budget applies.
- The product reports research dispositions and future human-judgment
  conditions; it does not monitor, recommend, or execute.
- Completed Milestone 1–3 history remains unchanged.
- Milestone 4 is implemented and complete.

## 18. Future design questions

The following are unresolved future contracts, not blockers for this alignment:

- the exact standard-monthly-option definition;
- event-window date representation;
- the exact Delta convention, nearest-eligible-Delta resolution, tie handling,
  and expiration interaction;
- the exact ATM or near-ATM definition;
- mode-specific quote and liquidity qualification;
- asset-class and event-specific stress calibration;
- the annual convexity-budget contract decision;
- actual mature Skills, their gaps, adapters, and compositions;
- the final non-annual risk-budget record;
- quantitative derivation of monetization, reassessment, and exit thresholds;
- provider versus internal non-expiration pricing;
- final position-management-plan architecture;
- final event-to-underlying accepted contract;
- direct-entry resolution of incomplete structure descriptions; and
- code changes required for the Chinese beginner overview.
