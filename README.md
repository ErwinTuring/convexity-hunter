# Convexity Hunter

Convexity Hunter is an open-source research assistant for finding assets that deserve further investigation as potential positive-convexity opportunities. It combines world events and narratives, market evidence, and bounded-downside/nonlinear-payoff reasoning.

It does not predict market direction or place trades. Narratives generate hypotheses; evidence determines what merits deeper research.

## MVP scope

The first MVP will organize research into five small stages:

1. Observe relevant world events and narratives.
2. Gather market evidence.
3. Connect hypotheses to evidence.
4. Identify candidates with bearable downside and nonlinear payoff potential.
5. Produce an evidence-based investigation report without unsupported scores.

## Current status

The repository contains only the initial project skeleton and documentation. Market scanning, external APIs, LLMs, MCP, Skills, and trading integrations are not implemented.

## Run the synthetic report

The example report uses invented demonstration values. It is not current market analysis and does not indicate that the scanner or agent is operational.

Run it with:

```text
PYTHONPATH=src python3 examples/sample_candidate_report.py
```

The checked-in output is available at `data/samples/sample-candidate-report.md`.

## Development

Python 3.9 or later is required. Source code will live under `src/convexity_hunter`, with tests under `tests`.
