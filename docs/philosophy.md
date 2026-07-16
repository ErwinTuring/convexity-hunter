# Project Philosophy

Convexity Hunter searches for **cheap positive convexity**, not market direction. It looks for payoff structures where maximum loss is explicitly bounded, quantifiable, and bearable, while gains increase nonlinearly under defined market-move scenarios.

## Convexity belongs to a structure

An asset is not automatically convex. Convexity belongs to a specific payoff structure or portfolio. Every candidate must eventually identify a concrete structure: instrument, direction, strike if applicable, expiration if applicable, and position-size assumptions.

“Bounded downside” must be evaluated for the total position, not for one instrument in isolation. A finite maximum loss is not enough. The loss must also be bearable relative to the assumed portfolio size.

## Costs determine whether convexity is cheap

Positive convexity is not automatically attractive. The system must investigate whether it appears underpriced relative to its costs and plausible payoff paths.

Real costs include option premium, theta decay, bid-ask spreads, commissions, and the accumulated cost of repeated failed bets. These costs belong in the total-position analysis.

## Narratives create testable hypotheses

Events and narratives generate hypotheses; they never become proof. Market evidence determines whether a hypothesis deserves further investigation.

Every hypothesis must state falsification conditions: observations or evidence that would weaken or reject it. A compelling story that cannot be tested is not sufficient.

## Reports must show uncertainty honestly

Every report must clearly separate:

- observed facts,
- model estimates,
- assumptions, and
- AI interpretations.

The system should prefer ranges, scenarios, and evidence strength over unsupported precise probabilities or scores. It should make downside, costs, uncertainty, and reasons for rejection visible.

## Humans make the decisions

Convexity Hunter is an investigation assistant, not a recommendation engine or autonomous trading bot. It organizes evidence and helps prioritize further research. The human user remains responsible for portfolio-level sizing and all investment or trading decisions.
