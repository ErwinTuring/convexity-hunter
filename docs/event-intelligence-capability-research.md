# Event Intelligence Capability Research v0.1

## Status and scope

This bounded research checkpoint evaluates reusable capabilities before any
Event Intelligence contract or adapter is implemented. It does not install a
Skill, select securities, rank investments, retrieve option chains, or create
an orchestration framework.

The product requirement is narrower than general investment research:

```text
source-backed event
    -> explicit fact and interpretation separation
    -> one or more resolved US equity/ETF underlyings
    -> disclosed impact path
    -> distribution-change hypothesis
    -> expected event window
    -> uncertainty, conflicts, and incomplete-result handling
```

Event Intelligence forms hypotheses. It supplies no market price, IV, Greek,
probability, opportunity score, trade recommendation, or proof that convexity
is underpriced.

## Capability review

| Capability | Useful role | Material gap | MVP disposition |
| --- | --- | --- | --- |
| Native web search and browser research | Flexible discovery and direct access to primary sources | Runtime-specific, nondeterministic, and has no stable typed output or producer version | Permitted research mechanism behind the accepted contract; not a product authority by itself |
| [`last30days`](https://github.com/mvanhorn/last30days-skill) | Recent community, news, and trend reconnaissance across social and web sources | Engagement-weighted synthesis, extensive optional credentials and source dependencies, mutable output workflow, and community statements that remain leads rather than authoritative facts | Optional future lead generator only; never sufficient evidence for acceptance |
| [`Serenity.skill`](https://github.com/muxuuu/serenity-skill) | Supply-chain mapping, source grading, counter-evidence, and falsification prompts | Its native workflow ranks layers and companies, uses a scorecard, and reaches broader investment-research priorities outside the current non-ranking boundary | Optional future hypothesis-method adapter; do not import rankings, scores, or security recommendations |
| [GDELT](https://docs.gdeltcloud.com/api-reference/events/search-events) | Broad multilingual event and article discovery | Automated coding is not source authority; live event metrics are not generally point-in-time vintaged; empty results do not prove no real-world event | Optional future discovery index; accepted facts must cite the underlying sources |
| [SEC EDGAR submissions](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Authoritative, unauthenticated, near-real-time issuer filings and stable company identity metadata | Covers issuer disclosures rather than the full world-event universe and does not supply an event-to-underlying impact hypothesis | Preferred authoritative source for filing-driven cases; add an adapter only after a demonstrated use case |

No evaluated capability directly satisfies the complete product boundary.
This is expected: source discovery, source authority, hypothesis formation,
underlying identity resolution, and deterministic acceptance are distinct
responsibilities.

## Adopted MVP direction

1. Implement one provider-neutral, Skill-neutral Event Intelligence submission
   and deterministic acceptance result before integrating a specific Skill or
   event provider.
2. Keep Skill-native output outside the core. A future adapter may translate a
   bounded subset into the accepted submission without changing the native
   Skill or treating its prose, ranking, or score as authority.
3. Require structured source references. Observed facts must bind to at least
   one source; interpretations must identify the facts or sources they depend
   on.
4. Require aware observation time, explicit event-time methodology, and an
   inclusive expected event-window date range. Unknown or disputed time
   semantics remain explicit and cannot silently satisfy acceptance.
5. Reuse the existing provider-neutral `UnderlyingKey` for each hypothesized
   US equity or ETF. Narrative ticker text alone is insufficient identity.
6. Represent support, contradiction, uncertainty, and missing fields without
   a numeric confidence or probability score.
7. Acceptance means only that the event-to-underlying hypothesis is auditable
   enough to enter later discovery work. It does not establish candidate
   eligibility, contract existence, pricing evidence, or an investment view.

## First implementation boundary

The first work unit should contain only:

- immutable event source references;
- immutable observed-fact and interpretation statements;
- an inclusive expected event window;
- one submitted event-to-underlying hypothesis with explicit producer
  identity/version, impact path, distribution-change mode, supporting and
  contradictory evidence, uncertainty, and optional missing fields;
- a deterministic acceptance result with closed reason codes; and
- synthetic tests, including incomplete, conflicting, chronology, source
  closure, identity, and caller-order cases.

The first work unit should not contain:

- web search, scraping, feed polling, SEC or GDELT clients;
- installation or vendoring of `last30days` or Serenity;
- LLM invocation, prompt orchestration, ranking, scoring, or prose generation;
- event monitoring, alerts, scheduling, or state transitions;
- option discovery, structure generation, market data, screening, or report
  integration; or
- a generic plugin, provider, or knowledge framework.

## Follow-on gate

After the provider-neutral acceptance boundary is implemented and reviewed,
exercise it first with one repository-external, source-backed real event
submission. Only that result may justify the smallest adapter, with SEC EDGAR
preferred when the first event is filing-driven. Social/trend or Serenity
capabilities remain optional lead and methodology inputs rather than default
product dependencies.
